"""
ReturnWise Request Service
==========================
The ONLY write path used by the UI.

  submit_return_request()  validate input, then insert one request row
  process_return()         submit (idempotent) + run the workflow + re-read from the DB
  get_request_detail()     everything stored for one request (request, recommendation, timeline)

The returned data always comes from the database after the write, so the UI
shows what was really saved.
"""

import re
import json
import sqlite3
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import config
import database.repository as repo
import workflow

logger = logging.getLogger(__name__)

VALID_REASONS = {"defective", "wrong_item", "damaged", "changed_mind", "other"}

_INJECTION_PATTERNS = [
    r"(?i)\b(drop\s+table|truncate\s+table|delete\s+from|insert\s+into|update\s+\w+\s+set)\b",
    r"(?i)\b(exec|eval)\s*\(",
    r"__import__",
    r"os\.system",
    r"subprocess",
    r"<\s*script",
]


# ============================================================
# Validation + insert
# ============================================================

def validation_errors(order_id: str, reason: str, description: Optional[str]) -> dict:
    """Field -> message for every invalid input (empty dict means valid). No database access."""
    errors: dict[str, str] = {}
    order_id = (order_id or "").strip().upper()
    reason = (reason or "").strip().lower()
    description = (description or "").strip() or None

    if not order_id:
        errors["order_id"] = "Order ID is required."
    elif not re.match(config.ORDER_ID_PATTERN, order_id):
        errors["order_id"] = "Order ID may contain only letters, digits, '-' and '_' (max 32 characters)."
    if reason not in VALID_REASONS:
        errors["reason"] = f"Invalid reason '{reason}'. Choose one of: {', '.join(sorted(VALID_REASONS))}."
    if description and len(description) > config.MAX_DESCRIPTION_LENGTH:
        errors["description"] = f"Description is too long (max {config.MAX_DESCRIPTION_LENGTH} characters)."
    elif description and _looks_like_injection(description):
        logger.warning("Rejected suspicious description for order %s", order_id)
        errors["description"] = "Description contains unsupported characters or patterns."
    return errors


def validate_request_input(order_id: str, reason: str, description: Optional[str]) -> tuple[dict, Optional[str]]:
    """Return (cleaned_fields, first_error_message_or_None). Nothing touches the database here."""
    errors = validation_errors(order_id, reason, description)
    if errors:
        # report in form order so the first message is the most relevant one
        for field in ("order_id", "reason", "description"):
            if field in errors:
                return {}, errors[field]
    return {
        "order_id": (order_id or "").strip().upper(),
        "reason": (reason or "").strip().lower(),
        "description": (description or "").strip() or None,
    }, None


def submit_return_request(
    order_id: str,
    reason: str,
    description: Optional[str] = None,
    is_test: bool = False,
    client_token: Optional[str] = None,
) -> dict:
    """
    Validate and persist a new return request (does not run the agents).

    If `client_token` was already used, the existing request is returned with
    duplicate=True and nothing new is written. This stops a double click or a
    Streamlit rerun from creating two requests.

    Returns: success, request_id, duplicate, error
    """
    fields, error = validate_request_input(order_id, reason, description)
    if error:
        return {"success": False, "request_id": None, "duplicate": False, "error": error}

    if client_token:
        existing = repo.get_request_by_token(client_token)
        if existing:
            return {"success": True, "request_id": existing["request_id"], "duplicate": True, "error": None}

    request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    try:
        repo.create_return_request(
            request_id=request_id,
            order_id=fields["order_id"],
            reason=fields["reason"],
            description=fields["description"],
            submitted_at=datetime.now(timezone.utc).isoformat(),
            is_test=is_test,
            client_token=client_token,
        )
    except sqlite3.IntegrityError:
        # Two simultaneous submits with one token: the unique index let only one in.
        existing = repo.get_request_by_token(client_token) if client_token else None
        if existing:
            return {"success": True, "request_id": existing["request_id"], "duplicate": True, "error": None}
        logger.error("Integrity error while creating request")
        return {"success": False, "request_id": None, "duplicate": False,
                "error": "The request could not be saved. Please try again."}
    except Exception as exc:                       # noqa: BLE001
        logger.error("Failed to create return request: %s", type(exc).__name__)
        return {"success": False, "request_id": None, "duplicate": False,
                "error": "The request could not be saved. Please try again."}

    logger.info("[%s] request created for order %s", request_id, fields["order_id"])
    return {"success": True, "request_id": request_id, "duplicate": False, "error": None}


def _looks_like_injection(text: str) -> bool:
    """Reject obvious code/SQL payloads in free text (SQL itself is parameterised anyway)."""
    return any(re.search(p, text) for p in _INJECTION_PATTERNS)


# ============================================================
# Submit + run workflow + read back
# ============================================================

def process_return(
    order_id: str,
    reason: str,
    description: Optional[str] = None,
    is_test: bool = False,
    client_token: Optional[str] = None,
    fault: Optional[str] = None,
) -> dict:
    """
    Full path used by the form and the demo page.

    Returns: success (bool), request_id, duplicate, error, detail
      `detail` is read back from the database (never from memory), so what the
      UI displays is exactly what was persisted.
    """
    sub = submit_return_request(order_id, reason, description, is_test, client_token)
    if not sub["success"]:
        return {"success": False, "request_id": None, "duplicate": False,
                "error": sub["error"], "detail": None}
    request_id = sub["request_id"]

    if sub["duplicate"]:
        return {"success": True, "request_id": request_id, "duplicate": True,
                "error": None, "detail": get_request_detail(request_id)}

    stored = repo.get_return_request(request_id)
    wf = workflow.process_return_request(
        request_id=request_id,
        order_id=stored["order_id"],
        reason=stored["reason"],
        description=stored["description"],
        fault=fault,
    )
    detail = get_request_detail(request_id)
    saved = bool(detail["request"]) and detail["request"]["status"] != "pending"
    return {
        # "success" means: the workflow ran and its results are in the database.
        # A business outcome of 'failed' (e.g. unknown order) is still saved, so it is reported
        # through detail/outcome rather than as a system error.
        "success": saved and wf["final_result"].get("saved", False),
        "request_id": request_id,
        "duplicate": False,
        "error": wf.get("error") if not wf["success"] else None,
        "outcome": wf["outcome"],
        "detail": detail,
    }


# ============================================================
# Reads
# ============================================================

def get_request_history(limit: int = 50) -> list[dict]:
    return repo.get_recent_requests(limit=limit)


def get_request_detail(request_id: str) -> dict:
    """
    Request + recommendation + ordered execution timeline, all from the database.
    Each log row gets its stored JSON decoded into `output` / `input`.
    """
    request = repo.get_return_request(request_id)
    recommendation = repo.get_recommendation(request_id)
    logs = repo.get_agent_logs(request_id)
    for row in logs:
        row["output"] = _loads(row.get("output_json"))
        row["input"] = _loads(row.get("input_json"))
    return {"request": request, "recommendation": recommendation, "agent_logs": logs}


def _loads(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None
