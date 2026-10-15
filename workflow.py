"""
ReturnWise Workflow Orchestrator
=================================
Runs the five agents in order, manages the bounded correction loop, and saves
EVERYTHING the run produced in a single database transaction.

    1 Intake and Planning (Planner)
    2 Order and Policy Research (Research)
    3 Eligibility Evaluation (Executor)
    4 Resolution (Business Automation)
    5 Validation (Critic)
         |-- passed ------------------------------> validated recommendation
         `-- failed + correctable (max 1 attempt)
               6 Resolution (correction pass)
               7 Validation (revalidation)
                    |-- passed ---------------------> validated recommendation
                    `-- anything else ---------------> manual review

Rules enforced here:
  * Stop early (and record the remaining agents as SKIPPED) if Intake or Research fails.
  * A recommendation is only "validated" when the Critic's final verdict is "passed".
  * At most config.MAX_CORRECTION_ATTEMPTS correction passes.
  * success=True is returned only if the results were actually saved.
  * Nothing here moves money or contacts a customer: output is a RECOMMENDATION.
"""

import json
import uuid
import logging
from datetime import datetime, timezone

import config
import database.repository as repo
from agents import (
    intake_agent,
    research_agent,
    eligibility_agent,
    resolution_agent,
    validation_agent,
)

logger = logging.getLogger(__name__)

# (execution_order, display name, academic role)
AGENTS = {
    1: ("Intake and Planning Agent",      "Planner Agent"),
    2: ("Order and Policy Research Agent", "Research Agent"),
    3: ("Eligibility Evaluation Agent",   "Executor Agent"),
    4: ("Resolution Agent",               "Business Automation Agent"),
    5: ("Validation Agent",               "Critic Agent"),
}
CORRECTION_ORDER = 6      # Resolution Agent, correction pass
REVALIDATION_ORDER = 7    # Validation Agent, second look

# Test-only fault injection (Demo page / tests). Never used by the normal form.
FAULTS = ("wrong_amount", "wrong_action", "persistent_error")

PERSISTENCE_ERROR = (
    "The result could not be saved to the database, so this request is NOT recorded as completed."
)


# ============================================================
# Public entry point
# ============================================================

def process_return_request(
    request_id: str,
    order_id: str,
    reason: str,
    description: str | None,
    fault: str | None = None,
) -> dict:
    """
    Run the workflow for a request that already exists in return_requests.

    Returns a dict:
        success         True only if the run finished AND was saved
        outcome         'validated' | 'manual_review' | 'failed'
        request_id, workflow_steps (list of step records), final_result (dict),
        error           user-safe message or None
    """
    if fault is not None and fault not in FAULTS:
        raise ValueError(f"Unknown fault '{fault}'.")

    steps: list[dict] = []
    logger.info("[%s] workflow started", request_id)

    # ---- 1. Intake ----
    intake_in = {"order_id": order_id, "reason": reason, "description": description}
    intake_out = _run_agent(intake_agent.run, intake_in)
    _record(steps, 1, "agent", intake_in, intake_out, verdict=intake_out.get("status"))
    if intake_out["status"] == "error":
        return _stop_early(request_id, steps, intake_out, from_order=2)

    # ---- 2. Research ----
    research_out = _run_agent(research_agent.run, intake_out)
    _record(steps, 2, "agent", _brief(intake_out), research_out, verdict=research_out.get("status"))
    if research_out["status"] == "error":
        return _stop_early(request_id, steps, research_out, from_order=3)

    # ---- 3. Eligibility ----
    elig_in = {"research": "research output (order, policy, evidence)", "reason": intake_out["reason"]}
    eligibility_out = _run_agent(eligibility_agent.run, research_out, intake_out["reason"])
    _record(steps, 3, "agent", elig_in, eligibility_out, verdict=eligibility_out.get("eligibility"))
    if eligibility_out["status"] == "error":
        return _stop_early(request_id, steps, eligibility_out, from_order=4)

    # ---- 4. Resolution ----
    resolution_out = _run_agent(resolution_agent.run, intake_out, research_out, eligibility_out)
    if resolution_out["status"] == "error":
        _record(steps, 4, "agent", {"eligibility": eligibility_out.get("eligibility")},
                resolution_out, verdict=None)
        return _stop_early(request_id, steps, resolution_out, from_order=5)
    if fault:
        resolution_out = _inject_fault(resolution_out, fault, research_out["order"])
    _record(steps, 4, "agent", {"eligibility": eligibility_out.get("eligibility"),
                                "permitted_actions": eligibility_out.get("permitted_actions")},
            resolution_out, verdict=resolution_out.get("recommended_action"))

    # ---- 5. Validation (Critic) ----
    validation_out = _run_agent(validation_agent.run, resolution_out, research_out, eligibility_out)
    _record(steps, 5, "validation", _brief(resolution_out), validation_out,
            verdict=validation_out.get("validation_status"))

    correction_attempted = 0
    correction_details = None
    final_resolution = resolution_out
    final_validation = validation_out

    # ---- 6/7. One bounded correction, then revalidation ----
    if (
        validation_out.get("validation_status") == "failed"
        and validation_out.get("corrected_action")
        and correction_attempted < config.MAX_CORRECTION_ATTEMPTS
    ):
        correction_attempted += 1
        correction_details = validation_out.get("correction_details")

        corrected = resolution_agent.apply_correction(resolution_out, validation_out)
        if fault == "persistent_error":
            corrected = _inject_fault(corrected, fault, research_out["order"])
        _record(steps, CORRECTION_ORDER, "correction", _brief(validation_out), corrected,
                verdict=corrected.get("recommended_action"), name="Resolution Agent (correction)")

        revalidation_out = _run_agent(validation_agent.run, corrected, research_out, eligibility_out)
        _record(steps, REVALIDATION_ORDER, "revalidation", _brief(corrected), revalidation_out,
                verdict=revalidation_out.get("validation_status"),
                name="Validation Agent (revalidation)")

        final_resolution = corrected
        final_validation = revalidation_out

    # ---- Decide the outcome: only a PASSED final verdict is a validated recommendation ----
    validated = final_validation.get("validation_status") == "passed"
    if validated:
        action = final_resolution["recommended_action"]
        refund = final_resolution.get("refund_amount")
        policy_text = final_resolution.get("policy_explanation", "")
        # A validated 'manual_review' action means the Critic agreed a human must decide.
        request_status = "manual_review" if action == "manual_review" else "validated"
    else:
        # Never present an unvalidated action as the recommendation.
        action = "manual_review"
        refund = None
        proposed = final_resolution.get("recommended_action")
        policy_text = (
            "Automatic validation did not succeed"
            + (" even after one correction attempt" if correction_attempted else "")
            + f" (last proposed action '{proposed}' was NOT accepted). "
            "A human reviewer must decide. "
            + final_validation.get("explanation", "")
        )
        request_status = "manual_review"

    validation_status = "passed" if validated else "manual_review"
    recommendation = {
        "recommendation_id":   f"REC-{uuid.uuid4().hex[:8].upper()}",
        "order_id":            intake_out["order_id"],
        "eligibility_status":  final_resolution.get("eligibility_status", "manual_review"),
        "recommended_action":  action,
        "refund_amount":       refund,
        "policy_explanation":  policy_text,
        "validation_status":   validation_status,
        "validation_details":  final_validation.get("output_summary", ""),
        "correction_attempted": correction_attempted,
        "correction_details":  correction_details,
        "created_at":          _now(),
    }

    # ---- Save everything in ONE transaction; failure => no success ----
    try:
        repo.save_workflow_result(request_id, _db_rows(steps), recommendation, request_status)
    except Exception as exc:                      # noqa: BLE001 - reported, never swallowed
        logger.error("[%s] saving workflow result failed: %s", request_id, type(exc).__name__)
        _mark_failed(request_id, PERSISTENCE_ERROR)
        return _failure_result(request_id, steps, PERSISTENCE_ERROR, saved=False)

    logger.info("[%s] workflow finished: %s / %s", request_id, request_status, action)
    return {
        "success":        True,
        "outcome":        request_status,
        "request_id":     request_id,
        "workflow_steps": steps,
        "error":          None,
        "final_result": {
            "request_id":           request_id,
            "recommendation_id":    recommendation["recommendation_id"],
            "order_id":             recommendation["order_id"],
            "eligibility_status":   recommendation["eligibility_status"],
            "recommended_action":   action,
            "refund_amount":        refund,
            "policy_explanation":   policy_text,
            "validation_status":    validation_status,
            "validation_details":   recommendation["validation_details"],
            "validation_checks":    final_validation.get("checks_performed", []),
            "detected_errors":      final_validation.get("detected_errors", []),
            "correction_attempted": correction_attempted,
            "correction_details":   correction_details,
            "confidence":           final_resolution.get("confidence", ""),
            "saved":                True,
        },
    }


# ============================================================
# Helpers
# ============================================================

def _apply_correction(resolution_out: dict, validation_out: dict) -> dict:
    """Backward-compatible alias; the logic lives in the Resolution Agent."""
    return resolution_agent.apply_correction(resolution_out, validation_out)


def _run_agent(fn, *args) -> dict:
    """Call an agent; a crash becomes a recorded error, never a fake success."""
    try:
        return fn(*args)
    except Exception as exc:                      # noqa: BLE001
        logger.error("Agent %s crashed: %s", getattr(fn, "__module__", fn), type(exc).__name__)
        msg = f"The agent stopped unexpectedly ({type(exc).__name__}). No decision was made."
        return {
            "status": "error", "explanation": msg,
            "input_summary": "", "output_summary": msg,
        }


def _brief(out: dict) -> dict:
    """Small input record for the log: scalar fields of the previous agent's output."""
    return {k: v for k, v in out.items()
            if isinstance(v, (str, int, float, bool, type(None))) and k not in ("explanation",)}


def _record(steps, order, step_type, agent_input, output, verdict=None, name=None):
    """Append one real execution record (also becomes one agent_logs row)."""
    if name is None:
        name = AGENTS[order][0]
    role = AGENTS[order if order in AGENTS else (4 if order == CORRECTION_ORDER else 5)][1]
    steps.append({
        "agent":           name,
        "role":            role,
        "order":           order,
        "step_type":       step_type,
        "status":          output.get("status", "success"),
        "verdict":         verdict,
        "input":           agent_input,
        "output":          output,
        "executed_at":     _now(),
        "is_revalidation": step_type == "revalidation",
    })


def _db_rows(steps: list[dict]) -> list[dict]:
    rows = []
    for st in steps:
        out = st["output"]
        rows.append({
            "agent_name":      st["agent"],
            "agent_role":      st["role"],
            "execution_order": st["order"],
            "status":          st["status"],
            "step_type":       st["step_type"],
            "verdict":         st["verdict"],
            "input_summary":   out.get("input_summary", "") or "",
            "output_summary":  out.get("output_summary", "") or "",
            "explanation":     out.get("explanation", "") or "",
            "executed_at":     st["executed_at"],
            "input_json":      json.dumps(st["input"], default=str),
            "output_json":     json.dumps(out, default=str),
        })
    return rows


def _skipped_steps(steps: list[dict], from_order: int, reason: str) -> None:
    """Record the agents that never ran because the workflow stopped early."""
    for order in range(from_order, 6):
        name, _role = AGENTS[order]
        _record(
            steps, order, "skipped", {},
            {"status": "skipped", "input_summary": "", "output_summary": "Not executed.",
             "explanation": f"Skipped because an earlier agent stopped the workflow: {reason}"},
            verdict=None,
        )


def _stop_early(request_id: str, steps: list[dict], failed_out: dict, from_order: int) -> dict:
    """Intake/Research failure: record skipped agents, save, and report 'Processing Failed'."""
    reason = failed_out.get("explanation", "Processing stopped.")
    _skipped_steps(steps, from_order, reason)
    try:
        repo.save_workflow_result(request_id, _db_rows(steps), None, "failed", error_message=reason[:500])
    except Exception as exc:                      # noqa: BLE001
        logger.error("[%s] saving early-stop result failed: %s", request_id, type(exc).__name__)
        _mark_failed(request_id, PERSISTENCE_ERROR)
        return _failure_result(request_id, steps, PERSISTENCE_ERROR, saved=False)
    logger.info("[%s] workflow stopped early", request_id)
    return _failure_result(request_id, steps, reason, saved=True)


def _failure_result(request_id: str, steps: list[dict], message: str, saved: bool) -> dict:
    return {
        "success":        False,
        "outcome":        "failed",
        "request_id":     request_id,
        "workflow_steps": steps,
        "error":          message,
        "final_result": {
            "request_id":           request_id,
            "recommendation_id":    None,
            "order_id":             None,
            "eligibility_status":   None,
            "recommended_action":   None,
            "refund_amount":        None,
            "policy_explanation":   message,
            "validation_status":    "not_run",
            "validation_details":   "Workflow did not complete.",
            "validation_checks":    [],
            "detected_errors":      [message],
            "correction_attempted": 0,
            "correction_details":   None,
            "confidence":           "",
            "saved":                saved,
        },
    }


def _mark_failed(request_id: str, message: str) -> None:
    try:
        repo.mark_request_failed(request_id, message)
    except Exception as exc:                      # noqa: BLE001
        logger.error("[%s] could not even mark request failed: %s", request_id, type(exc).__name__)


def _inject_fault(resolution: dict, fault: str, order: dict) -> dict:
    """
    TEST ONLY: corrupt a resolution so the Critic has something to catch.
    The corruption is labelled inside the record so it can never be mistaken
    for a genuine agent mistake.
    """
    total = round(float(order["total_amount"]), 2)
    bad = dict(resolution)
    bad["recommended_action"] = "refund"
    bad["refund_amount"] = round(total * 0.1, 2) if fault == "wrong_amount" else total
    bad["fault_injected"] = fault
    bad["explanation"] = f"[TEST FAULT INJECTED: {fault}] " + resolution.get("explanation", "")
    bad["output_summary"] = (
        f"[TEST FAULT: {fault}] Action: refund. Recommended refund amount: ₹{bad['refund_amount']:,.2f}."
    )
    return bad


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
