"""
Agent 5 – Validation Agent  (Role: Critic Agent)

Responsibilities:
  - Independently recheck the proposed action against order data, policy,
    and the eligibility result.
  - Verify that refund amounts are correct (= order total_amount).
  - Detect unsupported recommendations, missing evidence, inconsistent
    statuses, and policy violations.
  - Verify that missing/unknown data has NOT been treated as approval.
  - Accept valid recommendations (PASSED) or reject invalid ones (FAILED).
  - If a correctable inconsistency is found, produce a corrected recommendation.
  - Recompute delivered / returnable / in-window from the raw order and policy rows
    (check 8) instead of trusting the earlier agents' conclusions.
  - Return explicit check results — NEVER approve blindly.

Input contract:
    {
        "resolution":  dict,   # Resolution Agent output
        "research":    dict,   # Research Agent output
        "eligibility": dict    # Eligibility Agent output
    }

Output contract:
    {
        "status":              "success",
        "validation_status":   "passed" | "failed" | "manual_review",
        "checks_performed":    list[dict],   # {check, passed, detail}
        "detected_errors":     list[str],
        "corrected_action":    str | None,
        "corrected_amount":    float | None,
        "corrected_eligibility": str | None,
        "correction_details":  str | None,
        "explanation":         str,
        "input_summary":       str,
        "output_summary":      str
    }
"""

import logging

from policies import rules

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"refund", "replacement", "reject", "manual_review"}


def run(resolution_output: dict, research_output: dict, eligibility_output: dict) -> dict:
    """
    Execute the Validation Agent.

    Performs a series of explicit checks. Returns PASSED, FAILED, or
    MANUAL_REVIEW. If FAILED and the error is correctable, returns a
    corrected recommendation.
    """
    action     = resolution_output.get("recommended_action", "")
    refund_amt = resolution_output.get("refund_amount")
    elig       = resolution_output.get("eligibility_status", "")
    order      = research_output.get("order") or {}
    policy     = research_output.get("policy") or {}
    permitted  = eligibility_output.get("permitted_actions", [])
    failed_rules = eligibility_output.get("failed_rules", [])

    input_summary = (
        f"action={action!r}, refund_amount={refund_amt}, "
        f"eligibility={elig!r}, permitted={permitted!r}"
    )

    checks = []
    errors = []

    # ---- Check 1: Action is a known value ----
    c1_passed = action in VALID_ACTIONS
    checks.append({
        "check":  "ACTION_IS_VALID",
        "passed": c1_passed,
        "detail": (
            f"Recommended action '{action}' is a recognised action."
            if c1_passed else
            f"Recommended action '{action}' is NOT a valid action. Valid: {VALID_ACTIONS}."
        ),
    })
    if not c1_passed:
        errors.append(f"Unknown action: '{action}'.")

    # ---- Check 2: Action is consistent with eligibility ----
    c2_passed, c2_detail, corrected_action, corrected_elig = _check_action_vs_eligibility(
        action, elig, permitted, failed_rules
    )
    checks.append({"check": "ACTION_CONSISTENT_WITH_ELIGIBILITY", "passed": c2_passed, "detail": c2_detail})
    if not c2_passed:
        errors.append(c2_detail)

    # ---- Check 3: Refund amount correctness ----
    expected_refund = round(float(order.get("total_amount", 0)), 2) if order else None
    c3_passed, c3_detail, corrected_amount = _check_refund_amount(
        action, refund_amt, expected_refund, permitted, policy
    )
    checks.append({"check": "REFUND_AMOUNT_CORRECT", "passed": c3_passed, "detail": c3_detail})
    if not c3_passed:
        errors.append(c3_detail)

    # ---- Check 4: Non-returnable categories must not be approved ----
    returnable = bool(policy.get("returnable", True))
    category   = order.get("category", "unknown")
    if not returnable and action in ("refund", "replacement"):
        c4_passed = False
        c4_detail = (
            f"Category '{category}' is non-returnable, but action '{action}' was recommended. "
            "This is a policy violation."
        )
        errors.append(c4_detail)
    else:
        c4_passed = True
        c4_detail = f"Category returnability check passed for action '{action}'."
    checks.append({"check": "NON_RETURNABLE_NOT_APPROVED", "passed": c4_passed, "detail": c4_detail})

    # ---- Check 5: Replacement-only categories must not issue cash refund ----
    replacement_only = bool(policy.get("replacement_only", False))
    if replacement_only and action == "refund":
        c5_passed = False
        c5_detail = (
            f"Category '{category}' is replacement-only, but a cash refund was recommended. "
            "Policy violation."
        )
        errors.append(c5_detail)
        if not corrected_action:
            corrected_action = "replacement"
            corrected_amount = None
            corrected_elig = "eligible"
    else:
        c5_passed = True
        c5_detail = "Replacement-only policy check passed."
    checks.append({"check": "REPLACEMENT_ONLY_RESPECTED", "passed": c5_passed, "detail": c5_detail})

    # ---- Check 6: Manual review cases must not be marked as approved ----
    if elig == "manual_review" and action not in ("manual_review",):
        c6_passed = False
        c6_detail = (
            f"Eligibility is 'manual_review' but action '{action}' was recommended instead of 'manual_review'."
        )
        errors.append(c6_detail)
        if not corrected_action:
            corrected_action = "manual_review"
            corrected_amount = None
            corrected_elig = "manual_review"
    else:
        c6_passed = True
        c6_detail = "Manual-review flag check passed."
    checks.append({"check": "MANUAL_REVIEW_RESPECTED", "passed": c6_passed, "detail": c6_detail})

    # ---- Check 7: Order status must be delivered for refund/replacement ----
    order_status = order.get("status", "unknown")
    if action in ("refund", "replacement") and order_status != "delivered":
        c7_passed = False
        c7_detail = (
            f"Order status is '{order_status}', but action '{action}' requires 'delivered' status."
        )
        errors.append(c7_detail)
        if not corrected_action:
            corrected_action = "reject"
            corrected_amount = None
            corrected_elig = "ineligible"
    else:
        c7_passed = True
        c7_detail = f"Order status '{order_status}' is consistent with action '{action}'."
    checks.append({"check": "ORDER_STATUS_CONSISTENT", "passed": c7_passed, "detail": c7_detail})

    # ---- Check 8: independently recompute the eligibility facts from raw order + policy ----
    c8_passed, c8_detail, c8_fixable = _check_facts_independently(
        elig, action, order, policy, research_output
    )
    checks.append({"check": "FACTS_INDEPENDENTLY_VERIFIED", "passed": c8_passed, "detail": c8_detail})
    if not c8_passed:
        errors.append(c8_detail)
        if c8_fixable and not corrected_action:
            corrected_action = "reject"
            corrected_amount = None
            corrected_elig = "ineligible"

    # ---- Determine validation outcome ----
    all_passed = all(c["passed"] for c in checks)

    # If only the refund amount is wrong but the action itself is correct,
    # corrected_amount is set but corrected_action may still be None.
    # In that case we can still correct by keeping the same action with the fixed amount.
    if not all_passed and corrected_amount is not None and corrected_action is None:
        corrected_action = action   # keep same action, just fix the amount
        if corrected_elig is None:
            corrected_elig = elig

    # The refund amount always follows the corrected action: the stored order total
    # for a refund, nothing for every other action.
    if corrected_action:
        corrected_amount = expected_refund if corrected_action == "refund" else None
        if corrected_action == "refund" and expected_refund is None:
            corrected_action = None   # nothing trustworthy to correct to -> manual review

    if all_passed:
        validation_status = "passed"
        correction_details = None
        explanation = (
            f"All {len(checks)} validation checks passed. "
            f"Recommendation '{action}' is approved by the Critic Agent."
        )
        corrected_action = None
        corrected_amount = None
        corrected_elig = None
    elif corrected_action:
        validation_status = "failed"
        correction_details = (
            f"Original action '{action}' (amount {refund_amt}) failed validation. "
            f"Corrected to '{corrected_action}'"
            + (f" with refund amount ₹{corrected_amount:,.2f}" if corrected_amount else " with no refund amount")
            + f". Errors detected: {'; '.join(errors)}"
        )
        explanation = (
            f"Validation FAILED. {len(errors)} error(s) found. "
            f"A corrected recommendation of '{corrected_action}' has been proposed."
        )
    else:
        validation_status = "manual_review"
        corrected_action = None
        corrected_amount = None
        corrected_elig = None
        correction_details = None
        explanation = (
            f"Validation FAILED with {len(errors)} error(s) and no automatic correction is possible. "
            "Flagging for manual review. "
            f"Errors: {'; '.join(errors)}."
        )

    return {
        "status":                 "success",
        "validation_status":      validation_status,
        "checks_performed":       checks,
        "detected_errors":        errors,
        "corrected_action":       corrected_action,
        "corrected_amount":       corrected_amount,
        "corrected_eligibility":  corrected_elig,
        "correction_details":     correction_details,
        "explanation":            explanation,
        "input_summary":          input_summary,
        "output_summary": (
            f"Validation: {validation_status.upper()}. "
            f"Checks: {sum(1 for c in checks if c['passed'])}/{len(checks)} passed. "
            + (f"Errors: {len(errors)}." if errors else "")
        ),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_facts_independently(
    elig: str, action: str, order: dict, policy: dict, research_output: dict
) -> tuple[bool, str, bool]:
    """
    The Critic does not trust the earlier agents' conclusions blindly: it recomputes
    the key facts (delivered? returnable? inside the window?) from the raw order and
    policy rows, using the shared date helpers.

    Returns (passed, detail, fixable). `fixable` means 'the safe correction is reject'.
    """
    delivery = order.get("delivery_date")
    window = policy.get("return_window_days")
    if not order or not policy or not delivery or window is None:
        return True, "Not verifiable from the supplied order/policy data (no delivery date); skipped.", False
    try:
        days = rules.days_since_delivery(delivery)
    except ValueError:
        return False, f"Delivery date '{delivery}' is not a valid date; facts cannot be verified.", False

    reported = research_output.get("days_since_delivery")
    if reported is not None and reported != days:
        return (
            False,
            f"Research evidence says {reported} days since delivery, but the order record gives {days}. "
            "Evidence is inconsistent.",
            False,
        )

    delivered = order.get("status") == "delivered"
    returnable = bool(policy.get("returnable"))
    in_window = rules.is_within_window(days, window)
    facts_ok = delivered and returnable and in_window
    approves = elig == "eligible" or action in ("refund", "replacement")
    if approves and not facts_ok:
        return (
            False,
            f"Recomputed facts (delivered={delivered}, returnable={returnable}, "
            f"in_window={in_window}, days={days}, window={window}) do not support approval.",
            True,
        )
    return (
        True,
        f"Recomputed facts: delivered={delivered}, returnable={returnable}, "
        f"in_window={in_window} ({days} days vs {window}-day window). Consistent with the decision.",
        False,
    )


def _check_action_vs_eligibility(
    action: str, elig: str, permitted: list, failed_rules: list
) -> tuple[bool, str, str | None, str | None]:
    """
    Verify the action is consistent with the eligibility result.
    Returns (passed, detail, corrected_action_or_None, corrected_elig_or_None).
    """
    corrected_action = None
    corrected_elig   = None

    if elig == "ineligible":
        if action != "reject":
            # Correctable: force to reject
            corrected_action = "reject"
            corrected_elig   = "ineligible"
            return (
                False,
                f"Eligibility is 'ineligible' (failed: {failed_rules}), "
                f"but action '{action}' was recommended. Should be 'reject'.",
                corrected_action, corrected_elig,
            )
        return True, "Ineligible order correctly mapped to 'reject'.", None, None

    if elig == "eligible":
        if action not in permitted and action != "manual_review":
            corrected_action = permitted[0] if permitted else "manual_review"
            corrected_elig   = "eligible"
            return (
                False,
                f"Eligible order has permitted actions {permitted}, "
                f"but action '{action}' is not in the list.",
                corrected_action, corrected_elig,
            )
        return True, f"Action '{action}' is in permitted list {permitted}.", None, None

    if elig == "manual_review":
        if action != "manual_review":
            corrected_action = "manual_review"
            corrected_elig   = "manual_review"
            return (
                False,
                f"Eligibility requires manual review, but action '{action}' was set.",
                corrected_action, corrected_elig,
            )
        return True, "Manual review correctly propagated.", None, None

    return False, f"Unexpected eligibility value '{elig}'.", None, None


def _check_refund_amount(
    action: str,
    refund_amt,
    expected_refund: float | None,
    permitted: list,
    policy: dict,
) -> tuple[bool, str, float | None]:
    """
    Verify refund amount rules.
    Returns (passed, detail, corrected_amount_or_None).
    """
    if action == "refund":
        if refund_amt is None:
            return (
                False,
                "Refund action is recommended but no refund amount was specified.",
                expected_refund,
            )
        if expected_refund is not None:
            diff = abs(round(float(refund_amt), 2) - expected_refund)
            if diff > 0.01:   # allow 1-paisa rounding tolerance
                return (
                    False,
                    f"Refund amount ₹{refund_amt:,.2f} does not match order total "
                    f"₹{expected_refund:,.2f} (difference: ₹{diff:,.2f}).",
                    expected_refund,
                )
        return (
            True,
            f"Refund amount ₹{refund_amt:,.2f} matches order total.",
            None,
        )

    elif action in ("reject", "manual_review", "replacement"):
        if refund_amt is not None and float(refund_amt) > 0:
            return (
                False,
                f"Action '{action}' should have no refund amount, "
                f"but ₹{refund_amt:,.2f} was found.",
                None,
            )
        return True, f"No refund amount for action '{action}'.", None

    return True, "Refund amount check not applicable.", None
