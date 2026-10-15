"""
Agent 3 – Eligibility Evaluation Agent  (Role: Executor Agent)

Responsibilities:
  - Apply deterministic Python business rules to research output.
  - Determine eligibility status and permitted resolution options.
  - Calculate refund amount (= order total_amount from the database).
  - Report each rule check with pass/fail and reason.
  - Never approve on ambiguous or missing data.

Input contract:
    research output dict (status="success") + reason (str)

Output contract:
    {
        "status":           "success" | "error",
        "eligibility":      "eligible" | "ineligible" | "manual_review",
        "permitted_actions": list[str],    # e.g. ["refund", "replacement"]
        "refund_amount":    float | None,
        "rule_checks":      list[dict],    # each: {rule, passed, reason}
        "failed_rules":     list[str],
        "explanation":      str,
        "input_summary":    str,
        "output_summary":   str
    }
"""

import logging

import config

logger = logging.getLogger(__name__)

# Statuses that indicate an order cannot be returned
INELIGIBLE_ORDER_STATUSES = {"pending", "processing", "cancelled", "returned"}


def run(research_output: dict, reason: str) -> dict:
    """
    Execute the Eligibility Evaluation Agent.

    Parameters
    ----------
    research_output : dict
        Output of the Research Agent (status must be "success").
    reason : str
        Normalised return reason from the Intake Agent.

    Returns
    -------
    dict
        Eligibility result (see module docstring).
    """
    order  = research_output.get("order")
    policy = research_output.get("policy")
    order_id_val = order.get('order_id') if order else None
    input_summary = (
        f"order_id={order_id_val!r}, "
        f"reason={reason!r}"
    )

    if not order or not policy:
        return _error("Missing order or policy data — cannot evaluate eligibility.",
                      input_summary)

    rule_checks = []
    failed_rules = []

    # ---- Rule 1: Order status must be 'delivered' ----
    status = order.get("status", "")
    r1_passed = status == "delivered"
    rule_checks.append({
        "rule":   "ORDER_STATUS_DELIVERED",
        "passed": r1_passed,
        "reason": (
            f"Order status is '{status}'. Only 'delivered' orders are eligible."
            if not r1_passed else
            f"Order status is 'delivered'."
        ),
    })
    if not r1_passed:
        failed_rules.append("ORDER_STATUS_DELIVERED")

    # ---- Rule 2: Product category must be returnable ----
    returnable = bool(policy.get("returnable"))
    r2_passed = returnable
    rule_checks.append({
        "rule":   "CATEGORY_RETURNABLE",
        "passed": r2_passed,
        "reason": (
            f"Category '{order.get('category')}' is non-returnable per policy {policy.get('policy_id')}."
            if not r2_passed else
            f"Category '{order.get('category')}' is returnable."
        ),
    })
    if not r2_passed:
        failed_rules.append("CATEGORY_RETURNABLE")

    # ---- Rule 3: Within return window (only if delivered) ----
    within_window = research_output.get("within_window")
    days = research_output.get("days_since_delivery")
    if status == "delivered":
        r3_passed = within_window is True
    else:
        r3_passed = False   # can't be in window if not delivered
    rule_checks.append({
        "rule":   "WITHIN_RETURN_WINDOW",
        "passed": r3_passed,
        "reason": (
            f"Return window is {policy.get('return_window_days')} days. "
            f"Days since delivery: {days}. "
            + ("Within window." if r3_passed else "Outside window.")
        ),
    })
    if not r3_passed:
        failed_rules.append("WITHIN_RETURN_WINDOW")

    # ---- Rule 4: Reason-specific checks ----
    r4_passed, r4_reason = _check_reason(reason, policy, order)
    rule_checks.append({
        "rule":   "REASON_POLICY_COMPATIBLE",
        "passed": r4_passed,
        "reason": r4_reason,
    })
    if not r4_passed:
        failed_rules.append("REASON_POLICY_COMPATIBLE")

    # ---- Rule 5: Unknown/missing data must not default to approval ----
    if within_window is None and status == "delivered":
        rule_checks.append({
            "rule":   "DELIVERY_DATE_KNOWN",
            "passed": False,
            "reason": "Delivery date is unknown; cannot confirm return window eligibility.",
        })
        failed_rules.append("DELIVERY_DATE_KNOWN")

    # ---- Rule 6: inconsistent order data is ambiguous -> manual review, never a guess ----
    data_issues = research_output.get("data_issues") or []
    if data_issues:
        rule_checks.append({
            "rule":   "ORDER_DATA_CONSISTENT",
            "passed": False,
            "reason": "Order data is inconsistent: " + " ".join(data_issues),
        })
        return _build_result(
            "manual_review", ["manual_review"], None,
            rule_checks, failed_rules + ["ORDER_DATA_CONSISTENT"],
            "Order records are inconsistent, so no automatic decision is made. Manual review required.",
            input_summary, order,
        )

    # ---- Reason = 'other' always requires manual review ----
    if reason == "other":
        eligibility = "manual_review"
        permitted_actions = ["manual_review"]
        refund_amount = None
        explanation = (
            "Return reason is 'other'. All unspecified-reason requests require manual review per policy."
        )
        return _build_result(
            eligibility, permitted_actions, refund_amount,
            rule_checks, failed_rules, explanation,
            input_summary, order,
        )

    # ---- Determine eligibility ----
    if failed_rules:
        eligibility = "ineligible"
        permitted_actions = []
        refund_amount = None
        explanation = (
            f"Request is INELIGIBLE. Failed rules: {', '.join(failed_rules)}. "
            "No refund or replacement will be issued."
        )
    else:
        eligibility = "eligible"
        replacement_only = bool(policy.get("replacement_only"))
        if replacement_only:
            permitted_actions = ["replacement"]
            refund_amount = None
            explanation = (
                f"Request is ELIGIBLE. Category '{order.get('category')}' is replacement-only "
                f"per policy {policy.get('policy_id')}. Refund not permitted."
            )
        else:
            permitted_actions = ["refund", "replacement"]
            refund_amount = round(float(order.get("total_amount", 0)), 2)
            # Guardrail: a refund must be positive and below the safety cap.
            if refund_amount <= 0 or refund_amount > config.MAX_REFUND_CAP:
                rule_checks.append({
                    "rule": "REFUND_WITHIN_CAP",
                    "passed": False,
                    "reason": f"Refund {refund_amount} is outside 0 < amount <= {config.MAX_REFUND_CAP}.",
                })
                return _build_result(
                    "manual_review", ["manual_review"], None,
                    rule_checks, failed_rules + ["REFUND_WITHIN_CAP"],
                    "Refund amount is outside the permitted range. Manual review required.",
                    input_summary, order,
                )
            explanation = (
                f"Request is ELIGIBLE. All {len(rule_checks)} rules passed. "
                f"Eligible for refund of ₹{refund_amount:,.2f} or replacement."
            )

    return _build_result(
        eligibility, permitted_actions, refund_amount,
        rule_checks, failed_rules, explanation,
        input_summary, order,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_reason(reason: str, policy: dict, order: dict) -> tuple[bool, str]:
    """Apply reason-specific policy rules."""
    category = order.get("category", "")
    damaged_allowed = bool(policy.get("damaged_allowed"))
    returnable = bool(policy.get("returnable"))

    if reason == "damaged":
        if not returnable:
            return False, (
                f"Damaged items in category '{category}' cannot be returned (non-returnable category)."
            )
        if not damaged_allowed:
            return False, (
                f"Policy {policy.get('policy_id')} does not allow damaged-item claims for category '{category}'."
            )
        return True, f"Damaged items are accepted for category '{category}'."

    if reason == "wrong_item":
        if not returnable:
            return False, (
                f"Wrong-item returns are not accepted for non-returnable category '{category}'."
            )
        return True, "Wrong-item claims are accepted for all returnable categories."

    if reason in ("defective", "changed_mind"):
        if not returnable:
            return False, (
                f"Reason '{reason}' not applicable for non-returnable category '{category}'."
            )
        return True, f"Reason '{reason}' is accepted for returnable category '{category}'."

    # Shouldn't reach here (intake normalises reasons), but be safe
    return False, f"Reason '{reason}' could not be evaluated."


def _error(message: str, input_summary: str) -> dict:
    return {
        "status":            "error",
        "eligibility":       "ineligible",
        "permitted_actions": [],
        "refund_amount":     None,
        "rule_checks":       [],
        "failed_rules":      ["MISSING_INPUT_DATA"],
        "explanation":       message,
        "input_summary":     input_summary,
        "output_summary":    message,
    }


def _build_result(
    eligibility, permitted_actions, refund_amount,
    rule_checks, failed_rules, explanation,
    input_summary, order,
) -> dict:
    output_summary = (
        f"Eligibility: {eligibility}. "
        f"Permitted actions: {permitted_actions}. "
        + (f"Recommended refund amount: ₹{refund_amount:,.2f}." if refund_amount else "No refund amount.")
    )
    return {
        "status":            "success",
        "eligibility":       eligibility,
        "permitted_actions": permitted_actions,
        "refund_amount":     refund_amount,
        "rule_checks":       rule_checks,
        "failed_rules":      failed_rules,
        "explanation":       explanation,
        "input_summary":     input_summary,
        "output_summary":    output_summary,
    }
