"""
Agent 4 – Resolution Agent  (Role: Business Automation Agent)

Responsibilities:
  - Use actual outputs from Intake, Research, and Eligibility agents.
  - Recommend: refund | replacement | reject | manual_review.
  - Explain the decision using supplied evidence and rules.
  - Never override a failed eligibility check without a documented rule permitting it.
  - Prepare a clear resolution summary.

Input contract:
    {
        "intake":      dict,   # Intake Agent output
        "research":    dict,   # Research Agent output
        "eligibility": dict    # Eligibility Agent output
    }

Output contract:
    {
        "status":                "success" | "error",
        "recommended_action":    str,          # refund | replacement | reject | manual_review
        "eligibility_status":    str,
        "refund_amount":         float | None,
        "supporting_evidence":   list[str],
        "policy_explanation":    str,
        "confidence":            str,          # high | medium | low
        "explanation":           str,
        "input_summary":         str,
        "output_summary":        str
    }
"""

import logging

logger = logging.getLogger(__name__)


def apply_correction(resolution_output: dict, validation_output: dict) -> dict:
    """
    Correction pass (second and last time this agent touches the decision).

    The Critic Agent says what is wrong and proposes corrected values; this
    function only copies those values into a new resolution record and keeps
    an audit note. It never invents values of its own.
    """
    corrected = dict(resolution_output)
    corrected["recommended_action"] = validation_output["corrected_action"]
    corrected["refund_amount"]      = validation_output.get("corrected_amount")
    if validation_output.get("corrected_eligibility"):
        corrected["eligibility_status"] = validation_output["corrected_eligibility"]
    note = validation_output.get("correction_details", "")
    corrected["explanation"] = f"[CORRECTED] {resolution_output.get('explanation', '')} -> {note}"
    corrected["policy_explanation"] = (
        f"{resolution_output.get('policy_explanation', '')} "
        f"[Corrected after Critic review: '{resolution_output.get('recommended_action')}' -> "
        f"'{validation_output['corrected_action']}'. Details are in the Errors and correction section.]"
    )
    amt = corrected["refund_amount"]
    corrected["output_summary"] = (
        f"Corrected action: {corrected['recommended_action']}. "
        + (f"Refund amount: ₹{amt:,.2f}." if amt else "No refund amount.")
    )
    corrected["input_summary"] = (
        f"original_action={resolution_output.get('recommended_action')!r}, "
        f"critic_corrected_action={validation_output['corrected_action']!r}"
    )
    corrected["status"] = "success"
    return corrected


def run(intake_output: dict, research_output: dict, eligibility_output: dict) -> dict:
    """
    Execute the Resolution Agent.

    Selects the recommended action from the permitted_actions list using
    explicit business logic. Never invents permissions not granted by the
    Eligibility Agent.
    """
    order_id   = intake_output.get("order_id", "UNKNOWN")
    reason     = intake_output.get("reason", "unknown")
    eligibility = eligibility_output.get("eligibility", "ineligible")
    permitted  = eligibility_output.get("permitted_actions", [])
    refund_amt = eligibility_output.get("refund_amount")

    input_summary = (
        f"order_id={order_id!r}, eligibility={eligibility!r}, "
        f"permitted={permitted!r}, refund_amount={refund_amt}"
    )

    # ---- Case 1: Manual review ----
    if eligibility == "manual_review":
        action = "manual_review"
        confidence = "low"
        policy_explanation = (
            "The return reason is 'other' or could not be clearly categorised. "
            "Manual review by a support agent is required before any resolution is issued."
        )
        explanation = (
            f"Resolution: MANUAL REVIEW REQUIRED for order '{order_id}'. "
            f"Reason: '{reason}'. The eligibility agent flagged this for human review."
        )

    # ---- Case 2: Ineligible ----
    elif eligibility == "ineligible":
        action = "reject"
        confidence = "high"
        failed = eligibility_output.get("failed_rules", [])
        policy_explanation = (
            "The return request does not meet the store's return policy requirements. "
            f"Failed rules: {', '.join(failed)}."
        )
        explanation = (
            f"Resolution: REJECT for order '{order_id}'. "
            f"Eligibility check failed. Failed rules: {', '.join(failed)}. "
            "No refund or replacement will be issued."
        )
        refund_amt = None   # enforce: no amount for rejected claims

    # ---- Case 3: Eligible ----
    elif eligibility == "eligible":
        if not permitted:
            # Should not happen, but treat defensively
            action = "manual_review"
            confidence = "low"
            policy_explanation = (
                "The order is eligible but no permitted actions were returned by the "
                "Eligibility Agent. Flagging for manual review."
            )
            explanation = f"Eligible order '{order_id}' has no permitted actions. Manual review required."
        elif "refund" in permitted:
            action = "refund"
            confidence = "high"
            policy_explanation = (
                f"The return request meets all policy requirements. "
                f"A full refund of ₹{refund_amt:,.2f} is RECOMMENDED per the applicable store policy (no payment is made by this system)."
            )
            explanation = (
                f"Resolution: REFUND ₹{refund_amt:,.2f} for order '{order_id}'. "
                f"Return reason: '{reason}'. All eligibility rules passed."
            )
        elif "replacement" in permitted:
            action = "replacement"
            confidence = "high"
            refund_amt = None   # replacements do not carry a cash amount
            policy_explanation = (
                "The product category is replacement-only per store policy. "
                "A replacement item will be dispatched instead of a cash refund."
            )
            explanation = (
                f"Resolution: REPLACEMENT for order '{order_id}'. "
                f"Category policy requires replacement instead of refund."
            )
        else:
            # Unknown permitted action
            action = "manual_review"
            confidence = "low"
            policy_explanation = "Permitted actions could not be resolved. Manual review required."
            explanation = f"Unrecognised permitted actions {permitted} for order '{order_id}'."
    else:
        # Unexpected eligibility value
        action = "manual_review"
        confidence = "low"
        policy_explanation = f"Unexpected eligibility status '{eligibility}'. Manual review required."
        explanation = f"Unexpected eligibility '{eligibility}' for order '{order_id}'."

    # Evidence shown to the user: research facts + one line per eligibility rule
    supporting_evidence_str = [
        str(e) if not isinstance(e, str) else e for e in research_output.get("evidence", [])
    ]
    for rc in eligibility_output.get("rule_checks", []):
        mark = "PASS" if rc.get("passed") else "FAIL"
        supporting_evidence_str.append(f"[{mark}] {rc.get('rule')}: {rc.get('reason')}")

    return {
        "status":              "success",
        "recommended_action":  action,
        "eligibility_status":  eligibility,
        "refund_amount":       refund_amt,
        "supporting_evidence": supporting_evidence_str,
        "policy_explanation":  policy_explanation,
        "confidence":          confidence,
        "explanation":         explanation,
        "input_summary":       input_summary,
        "output_summary": (
            f"Action: {action}. "
            + (f"Recommended refund amount: ₹{refund_amt:,.2f}." if refund_amt else "No refund amount.")
        ),
    }
