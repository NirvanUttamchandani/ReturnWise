"""
Demo and testing scenarios.

Each scenario states an EXPECTED result. `run_scenario` executes the real
workflow (marked is_test in the database), then compares the expectation with
what was actually READ BACK from the database. A scenario passes only if every
expected value matches; clicking the button never counts as a pass.
"""

import database.repository as repo
import services.request_service as svc
from agents import intake_agent

SCENARIOS = [
    {"id": "SC-01", "title": "Valid return (within window)", "order_id": "ORD-001",
     "reason": "defective", "description": "TV stopped working after 5 days.",
     "expect": {"status": "validated", "action": "refund", "eligibility": "eligible",
                "refund": 45999.00, "validation": "passed", "corrections": 0}},
    {"id": "SC-02", "title": "Expired return window", "order_id": "ORD-002",
     "reason": "changed_mind", "description": "Ordered too many jackets.",
     "expect": {"status": "validated", "action": "reject", "eligibility": "ineligible",
                "refund": None, "validation": "passed", "corrections": 0}},
    {"id": "SC-03", "title": "Damaged product (within window)", "order_id": "ORD-003",
     "reason": "damaged", "description": "Chair leg cracked on arrival.",
     "expect": {"status": "validated", "action": "refund", "eligibility": "eligible",
                "refund": 12999.00, "validation": "passed", "corrections": 0}},
    {"id": "SC-04", "title": "Restricted product (digital licence)", "order_id": "ORD-006",
     "reason": "changed_mind", "description": "Do not need the licence.",
     "expect": {"status": "validated", "action": "reject", "eligibility": "ineligible",
                "refund": None, "validation": "passed", "corrections": 0}},
    {"id": "SC-05", "title": "Unknown order", "order_id": "FAKE-999",
     "reason": "defective", "description": "My order is broken.",
     "expect": {"status": "failed", "action": None, "eligibility": None,
                "refund": None, "validation": None, "corrections": 0,
                "skipped_orders": [3, 4, 5]}},
    {"id": "SC-06", "title": "Missing required field (no order ID)", "kind": "preflight",
     "order_id": "", "reason": "defective", "description": "Lost my order number.",
     "expect": {"service_rejects": True, "intake_error_field": "order_id", "rows_created": 0}},
    {"id": "SC-07", "title": "Manual-review case (reason = other)", "order_id": "ORD-012",
     "reason": "other", "description": "Complicated situation.",
     "expect": {"status": "manual_review", "action": "manual_review", "eligibility": "manual_review",
                "refund": None, "validation": "passed", "corrections": 0}},
    {"id": "SC-08", "title": "Replacement-only category (health/safety)", "order_id": "ORD-011",
     "reason": "defective", "description": "Oximeter gives wrong readings.",
     "expect": {"status": "validated", "action": "replacement", "eligibility": "eligible",
                "refund": None, "validation": "passed", "corrections": 0}},
    {"id": "SC-09", "title": "Intentionally incorrect amount -> Critic corrects", "order_id": "ORD-001",
     "reason": "defective", "description": "Test: refund amount corrupted to 10%.",
     "fault": "wrong_amount",
     "expect": {"status": "validated", "action": "refund", "eligibility": "eligible",
                "refund": 45999.00, "validation": "passed", "corrections": 1,
                "first_verdict": "failed", "step_types": ["correction", "revalidation"]}},
    {"id": "SC-10", "title": "Incorrect action on restricted item -> correction + revalidation",
     "order_id": "ORD-006", "reason": "changed_mind", "description": "Test: refund wrongly proposed.",
     "fault": "wrong_action",
     "expect": {"status": "validated", "action": "reject", "eligibility": "ineligible",
                "refund": None, "validation": "passed", "corrections": 1,
                "first_verdict": "failed", "step_types": ["correction", "revalidation"]}},
    {"id": "SC-11", "title": "Correction fails -> manual review", "order_id": "ORD-002",
     "reason": "changed_mind", "description": "Test: error survives the correction.",
     "fault": "persistent_error",
     "expect": {"status": "manual_review", "action": "manual_review", "validation": "manual_review",
                "refund": None, "corrections": 1, "first_verdict": "failed",
                "revalidation_verdict": "failed", "step_types": ["correction", "revalidation"]}},
    {"id": "SC-12", "title": "Already-returned order", "order_id": "ORD-008",
     "reason": "defective", "description": "Return it again.",
     "expect": {"status": "validated", "action": "reject", "eligibility": "ineligible",
                "refund": None, "validation": "passed", "corrections": 0}},
]


def get_scenarios() -> list[dict]:
    return SCENARIOS


def _check(name, expected, actual) -> dict:
    return {"check": name, "expected": expected, "actual": actual, "passed": expected == actual}


def run_scenario(scenario: dict) -> dict:
    """Execute one scenario and return {id, request_id, checks, passed}."""
    if scenario.get("kind") == "preflight":
        return _run_preflight(scenario)

    expect = scenario["expect"]
    result = svc.process_return(
        scenario["order_id"], scenario["reason"], scenario["description"],
        is_test=True, fault=scenario.get("fault"),
    )
    if not result["detail"]:
        return {"id": scenario["id"], "request_id": None, "passed": False,
                "checks": [_check("request accepted", True, False)], "error": result["error"]}

    detail = result["detail"]                      # read back from the database
    req, rec, logs = detail["request"], detail["recommendation"], detail["agent_logs"]
    checks = [_check("final status", expect["status"], req["status"])]
    if "action" in expect:
        checks.append(_check("recommended action", expect["action"], rec["recommended_action"] if rec else None))
    if "eligibility" in expect:
        checks.append(_check("eligibility", expect["eligibility"], rec["eligibility_status"] if rec else None))
    if "refund" in expect:
        checks.append(_check("refund amount", expect["refund"], rec["refund_amount"] if rec else None))
    if "validation" in expect:
        checks.append(_check("final validation", expect["validation"], rec["validation_status"] if rec else None))
    if "corrections" in expect:
        checks.append(_check("correction attempts", expect["corrections"], rec["correction_attempted"] if rec else 0))
    if "first_verdict" in expect:
        first = next((l["verdict"] for l in logs if l["step_type"] == "validation"), None)
        checks.append(_check("first validation verdict", expect["first_verdict"], first))
    if "revalidation_verdict" in expect:
        rv = next((l["verdict"] for l in logs if l["step_type"] == "revalidation"), None)
        checks.append(_check("revalidation verdict", expect["revalidation_verdict"], rv))
    if "step_types" in expect:
        have = [l["step_type"] for l in logs]
        checks.append(_check("steps recorded", expect["step_types"], [t for t in have if t in expect["step_types"]]))
    if "skipped_orders" in expect:
        skipped = [l["execution_order"] for l in logs if l["status"] == "skipped"]
        checks.append(_check("skipped agents (order)", expect["skipped_orders"], skipped))
    return {"id": scenario["id"], "request_id": result["request_id"],
            "checks": checks, "passed": all(c["passed"] for c in checks), "error": None}


def _run_preflight(scenario: dict) -> dict:
    """Missing-field scenario: nothing may be written, and Intake must name the field."""
    before = repo.count_requests()
    sub = svc.submit_return_request(scenario["order_id"], scenario["reason"], scenario["description"], is_test=True)
    after = repo.count_requests()
    intake = intake_agent.run({"order_id": scenario["order_id"], "reason": scenario["reason"],
                               "description": scenario["description"]})
    expect = scenario["expect"]
    checks = [
        _check("service rejects input", expect["service_rejects"], not sub["success"]),
        _check("rows created", expect["rows_created"], after - before),
        _check("Intake flags field", expect["intake_error_field"],
               "order_id" if "order_id" in intake.get("missing_fields", []) else None),
    ]
    return {"id": scenario["id"], "request_id": None, "checks": checks,
            "passed": all(c["passed"] for c in checks), "error": sub["error"]}
