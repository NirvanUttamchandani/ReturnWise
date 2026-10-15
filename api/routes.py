"""HTTP endpoints. Each one calls an existing service function and shapes the JSON."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

import config
import services.demo_service as demo
import services.presentation as pres
import services.reporting_service as rep
import services.request_service as svc
from api import serializers
from api.schemas import CreateReturnBody

logger = logging.getLogger("returnwise.api")
router = APIRouter()

STATUSES = ("pending", "validated", "manual_review", "failed")
ACTIONS = ("refund", "replacement", "reject", "manual_review")


def _err(status: int, code: str, message: str, fields: dict | None = None, **extra) -> JSONResponse:
    from api.main import error_body          # local import: main imports this module
    return JSONResponse(status_code=status, content=error_body(code, message, fields, **extra))


# ------------------------------------------------------------------ system
@router.get("/health")
def health():
    """Liveness plus a real database read (so 'ok' means the data layer works)."""
    try:
        orders = len(rep.get_all_orders())
    except Exception:                                   # noqa: BLE001
        return _err(503, "database_unavailable", "The database could not be read.")
    return {"status": "ok", "version": config.APP_VERSION, "reference_date": config.REFERENCE_DATE_STR,
            "sample_orders": orders}


@router.get("/meta")
def meta():
    """Static vocabulary for forms and filters, so the frontend never hardcodes backend values."""
    return {
        "reasons": [{"value": r, "label": l} for r, l in (
            ("defective", "Defective or not working"), ("wrong_item", "Wrong item received"),
            ("damaged", "Arrived damaged"), ("changed_mind", "Changed my mind"),
            ("other", "Other (needs manual review)"))],
        "statuses": [{"value": s, "label": pres.STATUS_LABELS[s]} for s in STATUSES],
        "actions": [{"value": a, "label": pres.ACTION_LABELS[a]} for a in ACTIONS],
        "max_description_length": config.MAX_DESCRIPTION_LENGTH,
        "reference_date": config.REFERENCE_DATE_STR,
    }


@router.get("/orders")
def orders():
    """Sample orders from the database, for the order picker."""
    return {"orders": [
        {"order_id": o["order_id"], "product_name": o["product_name"], "category": o["category"],
         "status": o["status"], "total_amount": o["total_amount"]}
        for o in rep.get_all_orders()]}


# ------------------------------------------------------------------ metrics
@router.get("/metrics")
def metrics(include_tests: bool = False):
    m = rep.get_dashboard_metrics(include_tests=include_tests)
    by_status = rep.get_status_breakdown(include_tests)
    breakdown = {s: by_status.get(s, 0) for s in STATUSES}
    breakdown["validated"] += by_status.get("approved", 0) + by_status.get("rejected", 0)   # legacy v1.0 rows
    return {
        "include_tests": include_tests,
        "metrics": m,
        "status_breakdown": breakdown,
        "validation_failures": [serializers.summary(r) for r in rep.get_attention("validation_failure", include_tests)],
        "manual_review_cases": [serializers.summary(r) for r in rep.get_attention("manual_review", include_tests)],
    }


# ------------------------------------------------------------------ requests
@router.post("/requests")
def create_request(body: CreateReturnBody):
    """
    Validate, save and process a return request with the real workflow.
      201 created      (a business outcome of 'failed', e.g. unknown order, is still a saved result)
      200 duplicate    (same client_token: the existing request is returned, nothing new is made)
      422              invalid input, nothing written
      500              the result could not be saved
    """
    errors = svc.validation_errors(body.order_id, body.reason, body.description)
    if errors:
        return _err(422, "validation_error", "Please correct the highlighted fields.", errors)

    result = svc.process_return(body.order_id, body.reason, body.description,
                                is_test=False, client_token=body.client_token)
    if not result["request_id"]:
        return _err(500, "persistence_failed", result["error"] or "The request could not be saved.")
    if not result["success"]:
        return _err(500, "persistence_failed",
                    "The result could not be saved, so this request is NOT recorded as completed.",
                    request_id=result["request_id"])
    payload = serializers.detail(result["detail"])
    payload["duplicate"] = result["duplicate"]
    return JSONResponse(status_code=200 if result["duplicate"] else 201, content=payload)


@router.get("/requests")
def list_requests(
    q: str = Query("", max_length=64),
    status: str = Query("", max_length=20),
    action: str = Query("", max_length=20),
    include_tests: bool = False,
    limit: int = Query(15, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if status and status not in STATUSES:
        return _err(422, "validation_error", "Unknown status filter.", {"status": f"Use one of {list(STATUSES)}."})
    if action and action not in ACTIONS:
        return _err(422, "validation_error", "Unknown action filter.", {"action": f"Use one of {list(ACTIONS)}."})
    rows, total = rep.search_requests_page(q, status, action, include_tests, limit, offset)
    return {"items": [serializers.summary(r) for r in rows], "total": total, "limit": limit, "offset": offset}


def _bundle(request_id: str) -> dict:
    bundle = svc.get_request_detail(request_id)
    if not bundle["request"]:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' was not found.")
    return bundle


@router.get("/requests/{request_id}")
def get_request(request_id: str):
    return serializers.detail(_bundle(request_id))


@router.get("/requests/{request_id}/executions")
def get_executions(request_id: str):
    bundle = _bundle(request_id)
    return {"request_id": request_id, "steps": serializers.executions(bundle)}


# ------------------------------------------------------------------ testing lab
def _scenario(sc: dict) -> dict:
    return {"id": sc["id"], "title": sc["title"], "order_id": sc.get("order_id", ""),
            "reason": sc["reason"], "fault": sc.get("fault"), "kind": sc.get("kind", "workflow"),
            "expect": sc["expect"]}


@router.get("/scenarios")
def scenarios():
    return {"scenarios": [_scenario(s) for s in demo.get_scenarios()]}


def _run(sc: dict) -> dict:
    r = demo.run_scenario(sc)
    return {"id": sc["id"], "request_id": r.get("request_id"), "passed": r["passed"],
            "checks": r["checks"], "error": r.get("error")}


@router.post("/scenarios/run-all")
def run_all():
    return {"results": [_run(sc) for sc in demo.get_scenarios()]}


@router.post("/scenarios/{scenario_id}/run")
def run_one(scenario_id: str):
    sc = next((s for s in demo.get_scenarios() if s["id"] == scenario_id), None)
    if not sc:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' was not found.")
    return _run(sc)
