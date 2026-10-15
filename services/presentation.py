"""
Presentation helpers: turn stored status codes into the exact labels the UI may show.

IMPORTANT: ReturnWise only produces RECOMMENDATIONS. It never executes a refund,
so no label here says "Refunded" or "Payment completed".
"""

ACTION_LABELS = {
    "refund":        "Refund Recommended",
    "replacement":   "Replacement Recommended",
    "reject":        "Rejection Recommended",
    "manual_review": "Manual Review Required",
}

STATUS_LABELS = {
    "pending":       "Processing",
    "validated":     "Recommendation Validated",
    "manual_review": "Manual Review Required",
    "failed":        "Processing Failed",
    # legacy rows written by version 1.0
    "approved":      "Recommendation Validated",
    "rejected":      "Recommendation Validated",
}

# tone -> used by the UI to pick a colour class
TONES = {"refund": "ok", "replacement": "ok", "reject": "bad", "manual_review": "warn"}


def outcome(request: dict | None, recommendation: dict | None) -> dict:
    """
    Return {label, tone, status_label} describing the final state of a request.
    Only a request whose final Critic verdict is 'passed' gets an action label.
    """
    if not request:
        return {"label": "Unknown request", "tone": "muted", "status_label": "Unknown"}
    status = request.get("status", "pending")
    status_label = STATUS_LABELS.get(status, "Processing")

    if status == "failed":
        return {"label": "Processing Failed", "tone": "bad", "status_label": status_label}
    if status == "pending":
        return {"label": "Processing", "tone": "muted", "status_label": status_label}
    if status == "manual_review" or (recommendation or {}).get("validation_status") == "manual_review":
        return {"label": "Manual Review Required", "tone": "warn", "status_label": "Manual Review Required"}
    action = (recommendation or {}).get("recommended_action")
    if recommendation and recommendation.get("validation_status") == "passed" and action in ACTION_LABELS:
        return {"label": ACTION_LABELS[action], "tone": TONES[action], "status_label": status_label}
    return {"label": "Processing", "tone": "muted", "status_label": status_label}


def action_label(action: str | None) -> str:
    return ACTION_LABELS.get(action or "", "—")


def validation_label(validation_status: str | None) -> str:
    return {
        "passed": "Recommendation Validated",
        "manual_review": "Manual Review Required",
        "failed": "Validation Failed",
        "pending": "Pending",
        "not_run": "Not run",
    }.get(validation_status or "", "—")


def money(amount) -> str:
    return f"₹{amount:,.2f}" if amount is not None else "—"
