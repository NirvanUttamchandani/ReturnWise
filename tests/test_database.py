"""
Tests – Database Persistence
Tests that seed data is correct, write operations persist, and reads match.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import tempfile
import shutil

# Use an in-memory/temp DB for tests
@pytest.fixture(autouse=True)
def use_test_db(tmp_path, monkeypatch):
    """Override DB_PATH to use a fresh temporary database for each test."""
    test_db = str(tmp_path / "test_returnwise.db")
    import config
    monkeypatch.setattr(config, "DB_PATH", test_db)
    # Re-import db to pick up new path
    from database.db import init_db
    init_db()
    yield
    # Cleanup happens automatically (tmp_path is deleted after test)


class TestSeedData:

    def test_orders_seeded(self):
        from database.repository import get_all_orders
        orders = get_all_orders()
        assert len(orders) >= 20, f"Expected at least 20 orders, got {len(orders)}"

    def test_known_order_exists(self):
        from database.repository import get_order
        order = get_order("ORD-001")
        assert order is not None
        assert order["product_name"] == "UltraVision 55 TV"
        assert order["category"] == "electronics"
        assert order["status"] == "delivered"
        assert order["delivery_date"] == "2025-02-05"

    def test_total_amount_consistency(self):
        """quantity * unit_price must equal total_amount for all seeded orders."""
        from database.repository import get_all_orders
        for order in get_all_orders():
            expected = round(order["quantity"] * order["unit_price"], 2)
            actual   = round(order["total_amount"], 2)
            assert abs(expected - actual) < 0.01, (
                f"Order {order['order_id']}: qty={order['quantity']}, "
                f"unit_price={order['unit_price']}, total={order['total_amount']}"
            )

    def test_all_orders_have_valid_products(self):
        from database.db import get_connection
        conn = get_connection()
        bad = conn.execute("""
            SELECT o.order_id FROM orders o
            LEFT JOIN products p ON o.product_id = p.product_id
            WHERE p.product_id IS NULL
        """).fetchall()
        conn.close()
        assert len(bad) == 0, f"Orders with invalid product_id: {bad}"

    def test_policies_seeded(self):
        from database.repository import get_all_policies
        policies = get_all_policies()
        assert len(policies) >= 10

    def test_electronics_policy_exists(self):
        from database.repository import get_policy_by_category
        p = get_policy_by_category("electronics")
        assert p is not None
        assert p["return_window_days"] == 30
        assert p["returnable"] == 1


class TestReturnRequestPersistence:

    def test_create_and_retrieve_request(self):
        from database.repository import create_return_request, get_return_request
        create_return_request(
            request_id   = "REQ-TEST001",
            order_id     = "ORD-001",
            reason       = "defective",
            description  = "Test description",
            submitted_at = "2025-02-15T10:00:00+00:00",
            is_test      = True,
        )
        req = get_return_request("REQ-TEST001")
        assert req is not None
        assert req["order_id"]    == "ORD-001"
        assert req["reason"]      == "defective"
        assert req["is_test"]     == 1
        assert req["status"]      == "pending"

    def test_update_request_status(self):
        from database.repository import create_return_request, update_request_status, get_return_request
        create_return_request(
            request_id   = "REQ-TEST002",
            order_id     = "ORD-001",
            reason       = "defective",
            description  = None,
            submitted_at = "2025-02-15T10:00:00+00:00",
        )
        update_request_status("REQ-TEST002", "approved")
        req = get_return_request("REQ-TEST002")
        assert req["status"] == "approved"

    def test_create_and_retrieve_recommendation(self):
        from database.repository import (
            create_return_request, create_recommendation, get_recommendation
        )
        create_return_request(
            request_id   = "REQ-TEST003",
            order_id     = "ORD-001",
            reason       = "defective",
            description  = None,
            submitted_at = "2025-02-15T10:00:00+00:00",
        )
        create_recommendation(
            recommendation_id  = "REC-TEST001",
            request_id         = "REQ-TEST003",
            order_id           = "ORD-001",
            eligibility_status = "eligible",
            recommended_action = "refund",
            refund_amount      = 45999.00,
            policy_explanation = "Eligible within 30-day window.",
            created_at         = "2025-02-15T10:01:00+00:00",
        )
        rec = get_recommendation("REQ-TEST003")
        assert rec is not None
        assert rec["recommended_action"] == "refund"
        assert rec["refund_amount"]      == 45999.00
        assert rec["validation_status"]  == "pending"

    def test_validation_not_marked_approved_until_passed(self):
        """
        A recommendation must have validation_status='passed' to be considered approved.
        Verify that the default is 'pending' and not 'passed'.
        """
        from database.repository import (
            create_return_request, create_recommendation, get_recommendation
        )
        create_return_request(
            request_id   = "REQ-TEST004",
            order_id     = "ORD-001",
            reason       = "defective",
            description  = None,
            submitted_at = "2025-02-15T10:00:00+00:00",
        )
        create_recommendation(
            recommendation_id  = "REC-TEST002",
            request_id         = "REQ-TEST004",
            order_id           = "ORD-001",
            eligibility_status = "eligible",
            recommended_action = "refund",
            refund_amount      = 45999.00,
            policy_explanation = "Test.",
            created_at         = "2025-02-15T10:01:00+00:00",
        )
        rec = get_recommendation("REQ-TEST004")
        # NOT 'passed' yet
        assert rec["validation_status"] != "passed", (
            "Recommendation must not be marked 'passed' until the Validation Agent explicitly passes it."
        )

    def test_agent_log_persisted(self):
        from database.repository import (
            create_return_request, log_agent_execution, get_agent_logs
        )
        create_return_request(
            request_id   = "REQ-TEST005",
            order_id     = "ORD-001",
            reason       = "defective",
            description  = None,
            submitted_at = "2025-02-15T10:00:00+00:00",
        )
        log_agent_execution(
            request_id      = "REQ-TEST005",
            agent_name      = "Test Agent",
            agent_role      = "Planner",
            execution_order = 1,
            status          = "success",
            input_summary   = "order=ORD-001",
            output_summary  = "all good",
            explanation     = "Worked fine.",
            executed_at     = "2025-02-15T10:01:00+00:00",
        )
        logs = get_agent_logs("REQ-TEST005")
        assert len(logs) == 1
        assert logs[0]["agent_name"] == "Test Agent"
