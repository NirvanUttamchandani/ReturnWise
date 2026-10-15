"""
Agent 1 – Intake and Planning Agent  (Role: Planner)

Responsibilities:
  - Accept a raw return request (order_id, reason, description).
  - Validate required fields.
  - Normalise and extract structured data.
  - Produce a task plan for downstream agents.
  - Never invent order information.

Input contract:
    {
        "order_id":    str,          # may be empty/None
        "reason":      str,          # free-text or allowlisted value
        "description": str | None
    }

Output contract:
    {
        "status":          "success" | "error",
        "order_id":        str | None,
        "reason":          str | None,         # normalised
        "description":     str | None,
        "missing_fields":  list[str],
        "description_flags": list[str],     # suspicious customer text (never changes the decision)
        "task_plan":       list[str],
        "explanation":     str,
        "input_summary":   str,
        "output_summary":  str
    }
"""

import logging
import re

import config

logger = logging.getLogger(__name__)

VALID_REASONS = {"defective", "wrong_item", "damaged", "changed_mind", "other"}

# Customer free text is NEVER used by any decision rule. These patterns only
# raise a visible flag when the text tries to talk the system into ignoring policy.
_OVERRIDE_PATTERNS = [
    r"ignore (all |any |the |previous |prior |your )*(instructions|rules|polic(y|ies))",
    r"disregard (all |any |the |previous |prior |your )*(instructions|rules|polic(y|ies))",
    r"override (the |your |all )?(polic(y|ies)|rules|checks)",
    r"system prompt",
    r"you (must|have to|will) (approve|refund)",
    r"act as (an? )?(admin|manager|supervisor)",
]

# Alias map for common free-text synonyms → canonical reason codes
REASON_ALIASES = {
    "broken": "defective",
    "not working": "defective",
    "faulty": "defective",
    "doesnt work": "defective",
    "wrong product": "wrong_item",
    "incorrect item": "wrong_item",
    "received wrong": "wrong_item",
    "got wrong": "wrong_item",
    "arrived damaged": "damaged",
    "damage": "damaged",
    "cracked": "damaged",
    "scratched": "damaged",
    "no longer need": "changed_mind",
    "dont want": "changed_mind",
    "changed mind": "changed_mind",
    "want to return": "changed_mind",
}


def run(raw_input: dict) -> dict:
    """
    Execute the Intake and Planning Agent.

    Parameters
    ----------
    raw_input : dict
        Keys: order_id, reason, description

    Returns
    -------
    dict
        Structured agent output (see module docstring).
    """
    order_id    = _clean(raw_input.get("order_id"))
    reason_raw  = _clean(raw_input.get("reason"))
    description = _clean(raw_input.get("description"))

    missing_fields = []
    errors = []

    # --- Validate order_id (presence and safe format; existence is the Research Agent's job) ---
    if not order_id:
        missing_fields.append("order_id")
        errors.append("Order ID is missing.")
    elif not re.match(config.ORDER_ID_PATTERN, order_id):
        missing_fields.append("order_id")
        errors.append("Order ID has an invalid format (letters, digits, '-' and '_' only, max 32).")

    description_flags = _flag_description(description)

    # --- Normalise reason ---
    reason = _normalise_reason(reason_raw)
    if not reason:
        missing_fields.append("reason")
        errors.append(
            f"Return reason '{reason_raw}' is not recognised. "
            f"Valid reasons: {sorted(VALID_REASONS)}."
        )

    desc_preview = (description[:60] + "...") if description and len(description) > 60 else repr(description)
    input_summary = (
        f"order_id={order_id!r}, reason={reason_raw!r}, description={desc_preview}"
    )

    if missing_fields:
        explanation = (
            "Intake failed. Missing or invalid fields: "
            + ", ".join(errors)
            + " Please correct the input and resubmit."
        )
        return {
            "status":         "error",
            "order_id":       order_id,
            "reason":         None,
            "description":    description,
            "missing_fields": missing_fields,
            "description_flags": description_flags,
            "task_plan":      [],
            "explanation":    explanation,
            "input_summary":  input_summary,
            "output_summary": f"Validation failed: {', '.join(missing_fields)}",
        }

    task_plan = [
        f"1. Retrieve order '{order_id}' and associated product from the database.",
        "2. Look up the applicable store return policy for the product category.",
        "3. Evaluate eligibility using deterministic business rules.",
        "4. Generate a resolution recommendation based on eligibility and policy.",
        "5. Validate the recommendation using the Critic Agent.",
        "6. Store and display the final result.",
    ]

    explanation = (
        f"Intake completed successfully. Order ID '{order_id}' extracted. "
        f"Return reason normalised to '{reason}'. "
        f"A six-step task plan has been prepared for downstream agents."
        + (
            " NOTE: the free-text description contains wording that tries to influence the "
            "decision; it was flagged and ignored. Only database records and policy rules decide."
            if description_flags else ""
        )
    )

    return {
        "status":         "success",
        "order_id":       order_id,
        "reason":         reason,
        "description":    description,
        "missing_fields": [],
        "description_flags": description_flags,
        "task_plan":      task_plan,
        "explanation":    explanation,
        "input_summary":  input_summary,
        "output_summary": (
            f"Extracted: order_id={order_id!r}, reason={reason!r}. "
            f"Task plan with {len(task_plan)} steps prepared."
        ),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(value) -> str | None:
    """Strip and return None if empty."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _flag_description(description: str | None) -> list[str]:
    """Return the override phrases found in the customer text (informational only)."""
    if not description:
        return []
    lower = description.lower()
    return [p for p in _OVERRIDE_PATTERNS if re.search(p, lower)]


def _normalise_reason(raw: str | None) -> str | None:
    """
    Map raw reason text to a canonical reason code.
    1. Check allowlist directly.
    2. Check alias map (case-insensitive).
    3. Return None if unrecognised.
    """
    if not raw:
        return None
    lower = raw.lower().strip()
    if lower in VALID_REASONS:
        return lower
    for alias, canonical in REASON_ALIASES.items():
        if alias in lower:
            return canonical
    return None
