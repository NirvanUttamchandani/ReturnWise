"""
Tests – Return Policy Logic
Tests return-window calculations, category rules, and reason rules.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import date


# ---------------------------------------------------------------------------
# Return-window helper (mirrors eligibility_agent logic)
# ---------------------------------------------------------------------------
def days_since(delivery_str: str, reference_str: str = "2025-02-15") -> int:
    return (date.fromisoformat(reference_str) - date.fromisoformat(delivery_str)).days


def within_window(delivery_str: str, window_days: int, reference_str: str = "2025-02-15") -> bool:
    if window_days == 0:
        return False
    return days_since(delivery_str, reference_str) <= window_days


# ---------------------------------------------------------------------------
# Return-window calculations
# ---------------------------------------------------------------------------

class TestReturnWindow:

    def test_electronics_within_window(self):
        """ORD-001: delivered 2025-02-05, 30-day window → 10 days → eligible"""
        assert within_window("2025-02-05", 30) is True

    def test_clothing_expired_window(self):
        """ORD-002: delivered 2024-12-07, 60-day window → 70 days → expired"""
        assert within_window("2024-12-07", 60) is False

    def test_furniture_within_14day_window(self):
        """ORD-003: delivered 2025-02-10, 14-day window → 5 days → eligible"""
        assert within_window("2025-02-10", 14) is True

    def test_furniture_expired_14day_window(self):
        """ORD-020: delivered 2025-01-05, 14-day window → 41 days → expired"""
        assert within_window("2025-01-05", 14) is False

    def test_digital_zero_day_window(self):
        """Digital goods: window=0 → always False"""
        assert within_window("2025-02-13", 0) is False

    def test_boundary_last_day(self):
        """Delivered exactly 30 days ago → still within window (inclusive)"""
        assert within_window("2025-01-16", 30) is True

    def test_boundary_one_day_over(self):
        """Delivered 31 days ago → outside window"""
        assert within_window("2025-01-15", 30) is False

    def test_days_since_delivery_calculation(self):
        assert days_since("2025-02-05") == 10
        assert days_since("2024-12-07") == 70
        assert days_since("2025-02-10") == 5


# ---------------------------------------------------------------------------
# Category rules from the JSON policy
# ---------------------------------------------------------------------------

class TestCategoryRules:

    def _load_policy(self):
        import json, os
        policy_path = os.path.join(os.path.dirname(__file__), "..", "policies", "return_policy.json")
        with open(policy_path) as f:
            return json.load(f)

    def test_electronics_returnable(self):
        p = self._load_policy()
        assert p["categories"]["electronics"]["returnable"] is True
        assert p["categories"]["electronics"]["return_window_days"] == 30

    def test_digital_not_returnable(self):
        p = self._load_policy()
        assert p["categories"]["digital"]["returnable"] is False
        assert p["categories"]["digital"]["return_window_days"] == 0

    def test_health_safety_replacement_only(self):
        p = self._load_policy()
        assert p["categories"]["health_safety"]["replacement_only"] is True
        assert p["categories"]["health_safety"]["returnable"] is True

    def test_perishable_not_returnable(self):
        p = self._load_policy()
        assert p["categories"]["perishable"]["returnable"] is False

    def test_clothing_60_day_window(self):
        p = self._load_policy()
        assert p["categories"]["clothing"]["return_window_days"] == 60

    def test_furniture_14_day_window(self):
        p = self._load_policy()
        assert p["categories"]["furniture"]["return_window_days"] == 14


# ---------------------------------------------------------------------------
# Reason rules from the JSON policy
# ---------------------------------------------------------------------------

class TestReasonRules:

    def _load_policy(self):
        import json, os
        policy_path = os.path.join(os.path.dirname(__file__), "..", "policies", "return_policy.json")
        with open(policy_path) as f:
            return json.load(f)

    def test_other_requires_manual_review(self):
        p = self._load_policy()
        assert p["reason_rules"]["other"]["requires_manual_review"] is True

    def test_defective_eligible_if_in_window(self):
        p = self._load_policy()
        assert p["reason_rules"]["defective"]["always_eligible_if_in_window"] is True

    def test_wrong_item_eligible_if_in_window(self):
        p = self._load_policy()
        assert p["reason_rules"]["wrong_item"]["always_eligible_if_in_window"] is True
