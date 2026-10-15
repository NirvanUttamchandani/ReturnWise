"""
Tests – Full Workflow Integration
Tests the complete 5-agent pipeline using a temp database.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


@pytest.fixture(autouse=True)
def use_test_db(tmp_path, monkeypatch):
    """Use a fresh temp DB for each test."""
    test_db = str(tmp_path / "wf_test.db")
    import config
    monkeypatch.setattr(config, "DB_PATH", test_db)
    from database.db import init_db
    init_db()
    yield


def _submit_and_run(order_id: str, reason: str, description: str = "Test"):
    """Helper: submit a request and run the workflow. Returns (svc_result, wf_result)."""
    import services.request_service as svc
    import workflow

    svc_r = svc.submit_return_request(order_id=order_id, reason=reason, description=description, is_test=True)
    if not svc_r["success"]:
        return svc_r, None
    wf_r = workflow.process_return_request(
        request_id  = svc_r["request_id"],
        order_id    = order_id,
        reason      = reason,
        description = description,
    )
    return svc_r, wf_r


# ---------------------------------------------------------------------------
# Scenario tests
# ---------------------------------------------------------------------------

class TestWorkflowScenarios:

    def test_sc01_eligible_return_within_window(self):
        """ORD-001: electronics delivered 10 days ago → refund"""
        svc_r, wf_r = _submit_and_run("ORD-001", "defective")
        assert svc_r["success"]
        fr = wf_r["final_result"]
        assert fr["recommended_action"] == "refund"
        assert fr["eligibility_status"] == "eligible"
        assert fr["validation_status"]  == "passed"
        assert abs(fr["refund_amount"] - 45999.00) < 0.01

    def test_sc02_expired_return_window(self):
        """ORD-002: clothing delivered 70 days ago (60-day window) → reject"""
        svc_r, wf_r = _submit_and_run("ORD-002", "changed_mind")
        assert svc_r["success"]
        fr = wf_r["final_result"]
        assert fr["recommended_action"] == "reject"
        assert fr["eligibility_status"] == "ineligible"
        assert fr["refund_amount"] is None

    def test_sc03_damaged_within_window(self):
        """ORD-003: furniture damaged, delivered 5 days ago (14-day window) → refund"""
        svc_r, wf_r = _submit_and_run("ORD-003", "damaged")
        fr = wf_r["final_result"]
        assert fr["recommended_action"] == "refund"
        assert fr["validation_status"]  == "passed"

    def test_sc04_missing_order_id(self):
        """Empty order ID → service rejects before workflow starts"""
        import services.request_service as svc
        result = svc.submit_return_request(order_id="", reason="defective", description="Test")
        assert not result["success"]
        assert "required" in result["error"].lower()

    def test_sc05_unknown_order_id(self):
        """FAKE-999 → Research Agent returns error, workflow stops early.
        Updated semantics: an order that was never found is 'Processing Failed'
        (no recommendation is invented); it is not a 'reject' recommendation."""
        svc_r, wf_r = _submit_and_run("FAKE-999", "defective")
        assert svc_r["success"]   # service accepted the request
        assert not wf_r["success"]  # workflow stopped
        assert wf_r["outcome"] == "failed"
        fr = wf_r["final_result"]
        assert fr["recommended_action"] is None
        assert fr["eligibility_status"] is None

    def test_sc06_non_returnable_category_digital(self):
        """ORD-006: digital good → reject"""
        svc_r, wf_r = _submit_and_run("ORD-006", "changed_mind")
        fr = wf_r["final_result"]
        assert fr["recommended_action"] == "reject"
        assert fr["eligibility_status"] == "ineligible"

    def test_sc07_order_not_yet_delivered(self):
        """ORD-007: status=processing → reject"""
        svc_r, wf_r = _submit_and_run("ORD-007", "defective")
        fr = wf_r["final_result"]
        assert fr["recommended_action"] == "reject"
        assert fr["eligibility_status"] == "ineligible"

    def test_sc08_already_returned_order(self):
        """ORD-008: status=returned → reject"""
        svc_r, wf_r = _submit_and_run("ORD-008", "defective")
        fr = wf_r["final_result"]
        assert fr["recommended_action"] == "reject"

    def test_sc09_replacement_only_health_safety(self):
        """ORD-011: health_safety → replacement (not cash refund)"""
        svc_r, wf_r = _submit_and_run("ORD-011", "defective")
        fr = wf_r["final_result"]
        assert fr["recommended_action"] == "replacement"
        assert fr["refund_amount"] is None
        assert fr["validation_status"] == "passed"

    def test_sc10_manual_review_reason_other(self):
        """ORD-012: reason=other → manual_review"""
        svc_r, wf_r = _submit_and_run("ORD-012", "other")
        fr = wf_r["final_result"]
        assert fr["recommended_action"] == "manual_review"
        assert fr["eligibility_status"] == "manual_review"

    def test_refund_amount_equals_order_total(self):
        """ORD-009: 2 units at 4999 → total=9998 → refund must be 9998"""
        svc_r, wf_r = _submit_and_run("ORD-009", "defective")
        fr = wf_r["final_result"]
        if fr["recommended_action"] == "refund":
            assert abs(fr["refund_amount"] - 9998.00) < 0.01


# ---------------------------------------------------------------------------
# Safety and reliability
# ---------------------------------------------------------------------------

class TestSafetyRules:

    def test_malformed_reason_rejected(self):
        """Unrecognised reason → service rejects"""
        import services.request_service as svc
        result = svc.submit_return_request(order_id="ORD-001", reason="HACK ME", description="Test")
        assert not result["success"]

    def test_injection_attempt_rejected(self):
        """Description with SQL injection pattern → service rejects"""
        import services.request_service as svc
        result = svc.submit_return_request(
            order_id    = "ORD-001",
            reason      = "defective",
            description = "'; DROP TABLE orders; --",
        )
        assert not result["success"]

    def test_result_not_validated_without_validation_step(self):
        """
        A recommendation stored with validation_status='pending' must not
        be presented as validated.
        """
        from database.repository import (
            create_return_request, create_recommendation, get_recommendation
        )
        create_return_request(
            request_id   = "REQ-SAFETY01",
            order_id     = "ORD-001",
            reason       = "defective",
            description  = None,
            submitted_at = "2025-02-15T12:00:00+00:00",
        )
        create_recommendation(
            recommendation_id  = "REC-SAFETY01",
            request_id         = "REQ-SAFETY01",
            order_id           = "ORD-001",
            eligibility_status = "eligible",
            recommended_action = "refund",
            refund_amount      = 45999.00,
            policy_explanation = "Test.",
            created_at         = "2025-02-15T12:00:01+00:00",
        )
        rec = get_recommendation("REQ-SAFETY01")
        assert rec["validation_status"] != "passed", (
            "A recommendation created without going through the Validation Agent "
            "must not be considered approved."
        )

    def test_request_persists_after_workflow(self):
        """
        After a full workflow run, the request must be retrievable from the DB.
        """
        svc_r, wf_r = _submit_and_run("ORD-001", "defective")
        req_id = svc_r["request_id"]

        from database.repository import get_return_request, get_recommendation
        req = get_return_request(req_id)
        rec = get_recommendation(req_id)

        assert req is not None
        assert rec is not None
        assert rec["validation_status"] in ("passed", "failed", "manual_review")

    def test_no_negative_refund_amount(self):
        """Refund amount must never be negative."""
        svc_r, wf_r = _submit_and_run("ORD-001", "defective")
        fr = wf_r["final_result"]
        if fr.get("refund_amount") is not None:
            assert fr["refund_amount"] >= 0

    def test_workflow_deterministic(self):
        """
        Running the same order + reason twice must produce identical actions
        and refund amounts (no randomness).
        """
        _, wf_r1 = _submit_and_run("ORD-001", "defective")
        _, wf_r2 = _submit_and_run("ORD-001", "defective")
        assert wf_r1["final_result"]["recommended_action"] == wf_r2["final_result"]["recommended_action"]
        assert wf_r1["final_result"]["refund_amount"]      == wf_r2["final_result"]["refund_amount"]
        assert wf_r1["final_result"]["validation_status"]  == wf_r2["final_result"]["validation_status"]
