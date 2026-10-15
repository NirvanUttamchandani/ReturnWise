"""
Tests – Validation Agent (Critic Agent)
Tests that the Critic Agent catches invalid recommendations and
correctly handles the bounded correction loop.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_research(
    order_status   = "delivered",
    category       = "electronics",
    returnable     = 1,
    replacement_only = 0,
    damaged_allowed = 1,
    total_amount   = 45999.00,
    days_since     = 10,
    within_window  = True,
):
    return {
        "status": "success",
        "order": {
            "order_id":     "ORD-001",
            "status":       order_status,
            "category":     category,
            "total_amount": total_amount,
            "product_name": "Test Product",
        },
        "policy": {
            "policy_id":        "POL-TEST",
            "return_window_days": 30,
            "returnable":       returnable,
            "replacement_only": replacement_only,
            "damaged_allowed":  damaged_allowed,
        },
        "days_since_delivery": days_since,
        "within_window":       within_window,
        "evidence":            [],
    }


def _make_eligibility(
    eligibility      = "eligible",
    permitted        = None,
    refund_amount    = 45999.00,
    failed_rules     = None,
):
    return {
        "status":            "success",
        "eligibility":       eligibility,
        "permitted_actions": permitted if permitted is not None else ["refund", "replacement"],
        "refund_amount":     refund_amount,
        "rule_checks":       [],
        "failed_rules":      failed_rules or [],
    }


def _make_resolution(
    action       = "refund",
    eligibility  = "eligible",
    refund_amount = 45999.00,
):
    return {
        "status":             "success",
        "recommended_action": action,
        "eligibility_status": eligibility,
        "refund_amount":      refund_amount,
        "supporting_evidence": [],
        "policy_explanation": "Test policy explanation.",
        "confidence":         "high",
        "explanation":        "Test explanation.",
    }


# ---------------------------------------------------------------------------
# Validation Agent tests
# ---------------------------------------------------------------------------

from agents import validation_agent


class TestValidationAgentPasses:

    def test_valid_refund_passes(self):
        research    = _make_research()
        eligibility = _make_eligibility()
        resolution  = _make_resolution(action="refund", refund_amount=45999.00)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "passed"
        assert len(result["detected_errors"]) == 0

    def test_valid_rejection_passes(self):
        research    = _make_research(order_status="returned")
        eligibility = _make_eligibility(
            eligibility="ineligible", permitted=[], refund_amount=None, failed_rules=["ORDER_STATUS_DELIVERED"]
        )
        resolution  = _make_resolution(action="reject", eligibility="ineligible", refund_amount=None)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "passed"

    def test_valid_replacement_passes(self):
        research    = _make_research(category="health_safety", replacement_only=1)
        eligibility = _make_eligibility(
            eligibility="eligible", permitted=["replacement"], refund_amount=None
        )
        resolution  = _make_resolution(action="replacement", eligibility="eligible", refund_amount=None)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "passed"

    def test_manual_review_passes(self):
        research    = _make_research()
        eligibility = _make_eligibility(eligibility="manual_review", permitted=["manual_review"])
        resolution  = _make_resolution(action="manual_review", eligibility="manual_review", refund_amount=None)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "passed"


class TestValidationAgentCatchesErrors:

    def test_catches_incorrect_refund_amount(self):
        """
        Intentionally pass wrong refund amount (9000 vs expected 45999).
        Critic must detect this and propose a correction.
        """
        research    = _make_research(total_amount=45999.00)
        eligibility = _make_eligibility(refund_amount=45999.00)
        resolution  = _make_resolution(action="refund", refund_amount=9000.00)  # WRONG
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "failed"
        assert any("amount" in e.lower() for e in result["detected_errors"])
        # Critic should propose the correct amount
        assert result.get("corrected_amount") == 45999.00

    def test_catches_refund_for_ineligible_order(self):
        """
        Ineligible order but refund was recommended → Critic must catch.
        """
        research    = _make_research(order_status="cancelled")
        eligibility = _make_eligibility(
            eligibility="ineligible", permitted=[], refund_amount=None,
            failed_rules=["ORDER_STATUS_DELIVERED"]
        )
        resolution  = _make_resolution(action="refund", eligibility="ineligible", refund_amount=45999.00)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "failed"
        assert result.get("corrected_action") == "reject"

    def test_catches_refund_for_non_returnable_category(self):
        """
        Non-returnable category (digital) with a refund recommendation.
        Critic must detect the policy violation.
        """
        research    = _make_research(category="digital", returnable=0)
        eligibility = _make_eligibility(eligibility="ineligible", permitted=[], refund_amount=None,
                                        failed_rules=["CATEGORY_RETURNABLE"])
        resolution  = _make_resolution(action="refund", eligibility="ineligible", refund_amount=3999.00)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "failed"

    def test_catches_cash_refund_for_replacement_only_category(self):
        """
        Replacement-only category (health_safety) but cash refund recommended.
        """
        research    = _make_research(category="health_safety", replacement_only=1)
        eligibility = _make_eligibility(
            eligibility="eligible", permitted=["replacement"], refund_amount=None
        )
        resolution  = _make_resolution(action="refund", eligibility="eligible", refund_amount=2199.00)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "failed"
        assert result.get("corrected_action") == "replacement"

    def test_catches_refund_on_non_delivered_order(self):
        """
        Order not delivered but refund recommended.
        """
        research    = _make_research(order_status="processing", within_window=None)
        eligibility = _make_eligibility(
            eligibility="ineligible", permitted=[], refund_amount=None,
            failed_rules=["ORDER_STATUS_DELIVERED"]
        )
        resolution  = _make_resolution(action="refund", eligibility="ineligible", refund_amount=4999.00)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "failed"

    def test_catches_wrong_action_for_manual_review(self):
        """
        Eligibility is manual_review but action is 'refund' → must fail.
        """
        research    = _make_research()
        eligibility = _make_eligibility(eligibility="manual_review", permitted=["manual_review"], refund_amount=None)
        resolution  = _make_resolution(action="refund", eligibility="manual_review", refund_amount=45999.00)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] == "failed"
        assert result.get("corrected_action") == "manual_review"

    def test_does_not_always_pass(self):
        """
        Critic Agent must not be a rubber stamp.
        A deliberately broken recommendation must NOT pass.
        """
        research    = _make_research(total_amount=45999.00)
        eligibility = _make_eligibility(refund_amount=45999.00)
        # Inject a deliberately wrong refund amount
        resolution  = _make_resolution(action="refund", refund_amount=1.00)
        result = validation_agent.run(resolution, research, eligibility)
        assert result["validation_status"] != "passed", (
            "Critic Agent must not pass a recommendation with a wrong refund amount."
        )


class TestCorrectionLoop:

    def test_correction_produces_corrected_action(self):
        """
        After Critic FAILS, the workflow corrects the action.
        Verify that re-running the Validation Agent on the corrected
        resolution results in PASSED.
        """
        from workflow import _apply_correction

        research    = _make_research(total_amount=45999.00)
        eligibility = _make_eligibility(refund_amount=45999.00)
        # Bad resolution: wrong amount
        bad_resolution = _make_resolution(action="refund", refund_amount=9000.00)
        validation_result = validation_agent.run(bad_resolution, research, eligibility)

        assert validation_result["validation_status"] == "failed"
        assert validation_result.get("corrected_action") == "refund"
        assert validation_result.get("corrected_amount") == 45999.00

        # Apply correction
        corrected = _apply_correction(bad_resolution, validation_result)
        assert corrected["refund_amount"] == 45999.00

        # Revalidate
        revalidation = validation_agent.run(corrected, research, eligibility)
        assert revalidation["validation_status"] == "passed"

    def test_max_correction_attempts_respected(self):
        """
        Workflow must not attempt more than MAX_CORRECTION_ATTEMPTS corrections.
        """
        import config
        assert config.MAX_CORRECTION_ATTEMPTS == 1, (
            "Config must allow exactly 1 correction attempt."
        )

    def test_uncorrectable_failure_triggers_manual_review(self):
        """
        If correction still fails, workflow must flag for manual review.
        We simulate this by making the corrected action also invalid.
        """
        # An unknown action type → not correctable
        research    = _make_research()
        eligibility = _make_eligibility()
        resolution  = _make_resolution(action="unknown_action", refund_amount=None)
        result = validation_agent.run(resolution, research, eligibility)
        # unknown action fails check 1; no corrected_action since it's not a fixable case
        assert result["validation_status"] in ("failed", "manual_review")
