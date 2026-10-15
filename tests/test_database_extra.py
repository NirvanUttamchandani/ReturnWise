"""Database tests: fresh init, migration of a legacy file, history/search, associations, data quality."""

import json
import sqlite3
from datetime import date

import config
import database.repository as repo
from policies import rules


class TestInitialisation:
    def test_fresh_database_initialises_without_existing_file(self, tmp_path, monkeypatch):
        path = tmp_path / "nested" / "new.db"                      # directory does not exist yet
        monkeypatch.setattr(config, "DB_PATH", str(path))
        from database.db import init_db
        init_db()
        assert path.exists() and len(repo.get_all_orders()) >= 20

    def test_init_is_idempotent_and_keeps_data(self, db, process):
        process("ORD-001", "defective")
        from database.db import init_db
        init_db()
        init_db()
        assert repo.count_requests() == 1 and len(repo.get_all_orders()) >= 20

    def test_legacy_v1_database_is_migrated_not_destroyed(self, tmp_path, monkeypatch):
        path = str(tmp_path / "legacy.db")
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE return_requests (request_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
              reason TEXT NOT NULL, description TEXT, submitted_at TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending', is_test INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE agent_logs (log_id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
              agent_name TEXT NOT NULL, agent_role TEXT NOT NULL, execution_order INTEGER NOT NULL,
              status TEXT NOT NULL, input_summary TEXT, output_summary TEXT, explanation TEXT,
              executed_at TEXT NOT NULL);
            INSERT INTO return_requests VALUES ('REQ-OLD1','ORD-001','defective',NULL,'2025-01-01T00:00:00+00:00','approved',0);
            INSERT INTO agent_logs (request_id,agent_name,agent_role,execution_order,status,executed_at)
              VALUES ('REQ-OLD1','Intake and Planning Agent','Planner',1,'success','2025-01-01T00:00:00+00:00');
        """)
        conn.commit(); conn.close()
        monkeypatch.setattr(config, "DB_PATH", path)
        from database.db import init_db
        init_db()
        assert repo.get_return_request("REQ-OLD1")["status"] == "approved"      # old row kept
        logs = repo.get_agent_logs("REQ-OLD1")
        assert len(logs) == 1 and logs[0]["step_type"] == "agent" and logs[0]["output_json"] is None
        import services.request_service as svc
        assert svc.process_return("ORD-001", "defective")["success"]             # new code works on it


class TestPersistenceAndAssociation:
    def test_structured_output_round_trips(self, process):
        r = process("ORD-011", "defective")
        logs = r["detail"]["agent_logs"]
        res = next(l["output"] for l in logs if l["agent_name"] == "Resolution Agent")
        assert res["recommended_action"] == "replacement"
        assert json.loads(logs[3]["output_json"]) == res

    def test_logs_belong_to_their_own_request(self, process):
        a = process("ORD-001", "defective")["request_id"]
        b = process("ORD-002", "changed_mind")["request_id"]
        la, lb = repo.get_agent_logs(a), repo.get_agent_logs(b)
        assert {l["request_id"] for l in la} == {a} and {l["request_id"] for l in lb} == {b}
        assert json.loads(la[0]["output_json"])["order_id"] == "ORD-001"
        assert json.loads(lb[0]["output_json"])["order_id"] == "ORD-002"

    def test_detail_returned_equals_detail_stored(self, process):
        import services.request_service as svc
        r = process("ORD-003", "damaged")
        again = svc.get_request_detail(r["request_id"])
        assert again["recommendation"] == r["detail"]["recommendation"]
        assert len(again["agent_logs"]) == len(r["detail"]["agent_logs"]) == 5

    def test_duplicate_execution_order_is_blocked_by_index(self, process):
        r = process("ORD-001", "defective")["request_id"]
        import pytest
        with pytest.raises(sqlite3.IntegrityError):
            repo.log_agent_execution(r, "X", "Y", 1, "success", "", "", "", "t")


class TestSearchAndMetrics:
    def _seed(self, process):
        process("ORD-001", "defective"); process("ORD-002", "changed_mind")
        process("ORD-012", "other"); process("FAKE-999", "defective")

    def test_search_by_order_and_status_and_action(self, process):
        self._seed(process)
        assert {r["order_id"] for r in repo.search_requests("ORD-00")} == {"ORD-001", "ORD-002"}
        assert [r["order_id"] for r in repo.search_requests(status="failed")] == ["FAKE-999"]
        assert [r["order_id"] for r in repo.search_requests(action="refund")] == ["ORD-001"]
        rid = repo.search_requests("ORD-001")[0]["request_id"]
        assert [r["request_id"] for r in repo.search_requests(rid)] == [rid]

    def test_search_input_is_parameterised(self, process):
        self._seed(process)
        assert repo.search_requests("x' OR '1'='1") == []
        assert repo.count_requests() == 4

    def test_metrics_match_rows(self, process):
        self._seed(process)
        m = repo.get_dashboard_metrics()
        assert m["total"] == 4 and m["refund_recommended"] == 1 and m["rejected"] == 1
        assert m["manual_review"] == 1 and m["processing_failed"] == 1
        assert m["eligible"] == 1 and m["validation_failures"] == 0 and m["correction_attempts"] == 0

    def test_metrics_count_corrections_and_exclude_tests_on_request(self, db):
        import services.request_service as svc
        svc.process_return("ORD-001", "defective", is_test=True, fault="wrong_amount")
        svc.process_return("ORD-001", "defective", is_test=False)
        assert repo.get_dashboard_metrics(include_tests=True)["total"] == 2
        m = repo.get_dashboard_metrics(include_tests=False)
        assert m["total"] == 1 and m["correction_attempts"] == 0 and m["validation_failures"] == 0
        m_all = repo.get_dashboard_metrics()
        assert m_all["correction_attempts"] == 1 and m_all["validation_failures"] == 1


class TestSeedDataQuality:
    def test_every_order_is_consistent(self, db):
        from database.db import get_connection
        conn = get_connection()
        orders = [dict(r) for r in conn.execute(
            "SELECT o.*, p.unit_price AS product_unit_price, p.category, p.returnable AS p_ret "
            "FROM orders o JOIN products p ON p.product_id = o.product_id")]
        conn.close()
        assert len(orders) >= 20
        for o in orders:
            assert rules.check_order_integrity(o) == [], o["order_id"]
            assert date.fromisoformat(o["order_date"]) <= rules.reference_date()

    def test_every_category_has_a_policy_and_product_flags_agree(self, db):
        from database.db import get_connection
        conn = get_connection()
        bad = conn.execute("""SELECT p.product_id FROM products p
              LEFT JOIN return_policies r ON r.category = p.category
              WHERE r.policy_id IS NULL OR r.returnable != p.returnable
                 OR r.return_window_days != p.return_window_days""").fetchall()
        conn.close()
        assert bad == []

    def test_json_policy_document_matches_database_policies(self, db):
        doc = rules.load_policy_document()
        assert "FICTIONAL".lower() in doc["_meta"]["disclaimer"].lower()
        assert doc["global_rules"]["reference_date"] == config.REFERENCE_DATE_STR
        for p in repo.get_all_policies():
            j = doc["categories"][p["category"]]
            assert j["policy_id"] == p["policy_id"]
            assert j["return_window_days"] == p["return_window_days"]
            assert j["returnable"] == bool(p["returnable"])
            assert j["replacement_only"] == bool(p["replacement_only"])
            assert j["damaged_allowed"] == bool(p["damaged_allowed"])

    def test_integrity_checker_flags_bad_data(self):
        base = {"quantity": 1, "unit_price": 10.0, "total_amount": 10.0, "status": "delivered",
                "delivery_date": "2025-02-01", "order_date": "2025-01-30", "product_unit_price": 10.0}
        assert rules.check_order_integrity(base) == []
        assert rules.check_order_integrity({**base, "total_amount": 99.0})
        assert rules.check_order_integrity({**base, "delivery_date": None})
        assert rules.check_order_integrity({**base, "delivery_date": "2025-03-30"})   # future
        assert rules.check_order_integrity({**base, "delivery_date": "2025-01-01"})   # before order
        assert rules.check_order_integrity({**base, "status": "cancelled"})
        assert rules.check_order_integrity({**base, "product_unit_price": 12.0})
