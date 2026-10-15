"""
Turn service/repository results into JSON for the frontend.

No business rules here: labels come from services.presentation, decisions from the stored rows.
"""

import services.presentation as pres


def _outcome(request: dict, rec: dict | None) -> dict:
    o = pres.outcome(request, rec)
    return {"label": o["label"], "tone": o["tone"]}


def summary(row: dict) -> dict:
    """One row of the request list (a join of request + recommendation)."""
    request = {"status": row["status"]}
    rec = ({"recommended_action": row.get("recommended_action"),
            "validation_status": row.get("validation_status")}
           if row.get("recommended_action") else None)
    return {
        "request_id": row["request_id"],
        "order_id": row["order_id"],
        "reason": row["reason"],
        "submitted_at": row["submitted_at"],
        "status": row["status"],
        "is_test": bool(row.get("is_test")),
        "outcome": _outcome(request, rec),
        "recommended_action": row.get("recommended_action"),
        "action_label": pres.action_label(row.get("recommended_action")) if row.get("recommended_action") else None,
        "eligibility_status": row.get("eligibility_status"),
        "validation_status": row.get("validation_status"),
        "validation_label": pres.validation_label(row["validation_status"]) if row.get("validation_status") else None,
        "refund_amount": row.get("refund_amount"),
        "correction_attempted": bool(row.get("correction_attempted")),
        "error_message": row.get("error_message"),
    }


def _last_output(logs: list[dict], name_prefix: str | None = None, step_types: tuple = ()) -> dict:
    for log in reversed(logs):
        if not log.get("output"):
            continue
        if name_prefix and not log["agent_name"].startswith(name_prefix):
            continue
        if step_types and log["step_type"] not in step_types:
            continue
        return log["output"]
    return {}


def detail(bundle: dict) -> dict:
    """Request + final result, everything the Resolution Center needs (timeline is separate)."""
    req, rec, logs = bundle["request"], bundle["recommendation"], bundle["agent_logs"]
    research = _last_output(logs, "Order and Policy")
    resolution = _last_output(logs, "Resolution")
    first_validation = _last_output(logs, step_types=("validation",))
    final_validation = _last_output(logs, step_types=("validation", "revalidation"))
    order, policy = research.get("order") or {}, research.get("policy") or {}
    flags = (_last_output(logs, "Intake")).get("description_flags") or []

    return {
        "request": {
            "request_id": req["request_id"], "order_id": req["order_id"], "reason": req["reason"],
            "description": req["description"], "submitted_at": req["submitted_at"],
            "status": req["status"], "is_test": bool(req["is_test"]),
            "error_message": req.get("error_message"),
        },
        "outcome": _outcome(req, rec),
        "recommendation": None if not rec else {
            "recommendation_id": rec["recommendation_id"],
            "eligibility_status": rec["eligibility_status"],
            "recommended_action": rec["recommended_action"],
            "action_label": pres.action_label(rec["recommended_action"]),
            "refund_amount": rec["refund_amount"],
            "policy_explanation": rec["policy_explanation"],
            "validation_status": rec["validation_status"],
            "validation_label": pres.validation_label(rec["validation_status"]),
            "validation_details": rec["validation_details"],
            "correction_attempted": bool(rec["correction_attempted"]),
            "correction_details": rec["correction_details"],
            "created_at": rec["created_at"],
        },
        "order": None if not order else {
            "order_id": order.get("order_id"), "product_name": order.get("product_name"),
            "category": order.get("category"), "quantity": order.get("quantity"),
            "total_amount": order.get("total_amount"), "status": order.get("status"),
            "delivery_date": order.get("delivery_date"),
        },
        "policy": None if not policy else {
            "policy_id": policy.get("policy_id"), "category": policy.get("category"),
            "return_window_days": policy.get("return_window_days"),
            "returnable": bool(policy.get("returnable")),
            "replacement_only": bool(policy.get("replacement_only")),
            "notes": policy.get("notes"),
        },
        "evidence": resolution.get("supporting_evidence") or research.get("evidence") or [],
        "validation_checks": final_validation.get("checks_performed") or [],
        "first_validation_errors": first_validation.get("detected_errors") or [],
        "description_flagged": bool(flags),
        "manual_review_required": req["status"] == "manual_review",
        "is_recommendation_only": True,
    }


def executions(bundle: dict) -> list[dict]:
    """The complete stored execution timeline (one entry per agent_logs row, in order)."""
    return [
        {
            "execution_order": l["execution_order"], "agent_name": l["agent_name"],
            "agent_role": l["agent_role"], "step_type": l["step_type"], "status": l["status"],
            "verdict": l.get("verdict"), "input_summary": l.get("input_summary"),
            "output_summary": l.get("output_summary"), "explanation": l.get("explanation"),
            "executed_at": l["executed_at"], "input": l.get("input"), "output": l.get("output"),
        }
        for l in bundle["agent_logs"]
    ]
