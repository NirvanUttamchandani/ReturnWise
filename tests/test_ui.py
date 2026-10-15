"""UI integration tests using Streamlit's AppTest (runs app.py headlessly, no browser).

These check logic and text, NOT visual appearance; the look was inspected separately in a real browser."""

import os

import pytest
from streamlit.testing.v1 import AppTest

import database.repository as repo
import services.request_service as svc

APP = os.path.join(os.path.dirname(__file__), "..", "app.py")
PAGES = ["Dashboard", "New Return Request", "Agent Workflow", "Final Resolution",
         "Request History", "Demo and Testing"]


def new_app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def goto(at: AppTest, page: str) -> AppTest:
    at.sidebar.button(key=f"nav_{page}").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def all_text(at: AppTest) -> str:
    parts = []
    for coll in (at.markdown, at.success, at.error, at.warning, at.info, at.caption, at.code):
        parts += [str(getattr(e, "value", "")) for e in coll]
    parts += [f"{m.label} {m.value}" for m in at.metric]
    for df in at.dataframe:
        parts.append(df.value.to_csv())
    return "\n".join(parts)


@pytest.fixture
def app(db):
    return new_app()


class TestNavigation:
    def test_every_page_renders_and_active_item_is_highlighted(self, app):
        for page in PAGES:
            goto(app, page)
            assert app.session_state["page"] == page
            types = {b.key: b.proto.type for b in app.sidebar.button}
            assert types[f"nav_{page}"] == "primary"
            assert [k for k, t in types.items() if t == "primary"] == [f"nav_{page}"]

    def test_empty_states_do_not_crash(self, app):
        for page in ("Agent Workflow", "Final Resolution", "Request History"):
            goto(app, page)
            assert "No request" in all_text(app) or "0 request" in all_text(app)


class TestNewRequestForm:
    def test_empty_order_id_shows_error_and_writes_nothing(self, app):
        goto(app, "New Return Request")
        app.button(key="nr_submit").click().run()
        assert any("Order ID is required" in e.value for e in app.error)
        assert repo.count_requests() == 0

    def test_valid_submit_shows_backend_request_id_and_recommendation_wording(self, app):
        goto(app, "New Return Request")
        app.text_input(key="nr_order").set_value("ORD-001")
        app.button(key="nr_submit").click().run()
        rows = repo.search_requests()
        assert len(rows) == 1
        rid = rows[0]["request_id"]
        text = all_text(app)
        assert rid in text and "Refund Recommended" in text and "No payment has been made" in text
        assert app.session_state["selected_request"] == rid

    def test_unknown_order_gives_helpful_failure(self, app):
        goto(app, "New Return Request")
        app.text_input(key="nr_order").set_value("FAKE-999")
        app.button(key="nr_submit").click().run()
        assert any("not found" in e.value for e in app.error)
        assert "Processing Failed" in all_text(app)
        assert repo.search_requests()[0]["status"] == "failed"

    def test_rerun_with_same_token_does_not_duplicate(self, app):
        goto(app, "New Return Request")
        app.session_state["nr_token"] = "fixed-token"
        app.text_input(key="nr_order").set_value("ORD-001")
        app.button(key="nr_submit").click().run()
        assert repo.count_requests() == 1
        app.session_state["nr_token"] = "fixed-token"         # simulate a replayed submission
        app.button(key="nr_submit").click().run()
        assert repo.count_requests() == 1
        assert any("already processed" in w.value for w in app.warning)

    def test_sample_selector_fills_order_id(self, app):
        goto(app, "New Return Request")
        label = next(o for o in app.selectbox(key="nr_sample").options if o.startswith("ORD-003"))
        app.selectbox(key="nr_sample").select(label).run()
        assert app.text_input(key="nr_order").value == "ORD-003"

    def test_persistence_failure_is_shown_as_failure_without_stack_trace(self, app, monkeypatch):
        def broken(*a, **k):
            raise RuntimeError("disk exploded")
        monkeypatch.setattr(repo, "save_workflow_result", broken)
        goto(app, "New Return Request")
        app.text_input(key="nr_order").set_value("ORD-001")
        app.button(key="nr_submit").click().run()
        text = all_text(app)
        assert "Processing Failed" in text and "NOT recorded as completed" in text
        assert "Traceback" not in text and "disk exploded" not in text and "Saved." not in text


class TestSelectedRequestIsolation:
    def _two(self):
        a = svc.process_return("ORD-001", "defective")["request_id"]
        b = svc.process_return("ORD-002", "changed_mind")["request_id"]
        return a, b

    def test_workflow_page_shows_only_selected_request(self, app):
        a, b = self._two()
        app.session_state["selected_request"] = a
        goto(app, "Agent Workflow")
        text = all_text(app)
        assert a in text and "ORD-001" in text and "Refund Recommended" in text
        app.selectbox(key="wf_pick").select(b).run()
        text = all_text(app)
        assert "ORD-002" in text and "Rejection Recommended" in text
        assert "45,999" not in text                              # nothing left over from request A

    def test_resolution_page_follows_selection(self, app):
        a, b = self._two()
        app.session_state["selected_request"] = b
        goto(app, "Final Resolution")
        text = all_text(app)
        assert b in text and "Rejection Recommended" in text and "POL-CLTH-002" in text
        assert a not in text

    def test_timeline_after_restart_comes_from_database(self, db):
        rid = svc.process_return("ORD-001", "defective", fault="wrong_amount", is_test=True)["request_id"]
        fresh = new_app()                                         # brand-new session = 'restart'
        fresh.session_state["selected_request"] = rid
        goto(fresh, "Agent Workflow")
        text = all_text(fresh)
        assert "Correction loop" in text and "Resolution Agent (correction)" in text
        assert "Validation Agent (revalidation)" in text

    def test_failed_request_shows_skipped_agents(self, app):
        rid = svc.process_return("FAKE-999", "defective")["request_id"]
        app.session_state["selected_request"] = rid
        goto(app, "Agent Workflow")
        text = all_text(app)
        assert "Skipped" in "".join(m.value for m in app.markdown)
        assert "Failed" in "".join(m.value for m in app.markdown)


class TestDashboardAndHistory:
    def test_dashboard_numbers_come_from_database(self, app):
        svc.process_return("ORD-001", "defective")
        svc.process_return("ORD-002", "changed_mind")
        svc.process_return("ORD-012", "other")
        goto(app, "Dashboard")
        vals = {m.label: m.value for m in app.metric}
        assert vals["Requests processed"] == "3" and vals["Refund recommended"] == "1"
        assert vals["Rejection recommended"] == "1" and vals["Manual review"] == "1"

    def test_dashboard_excludes_test_runs_by_default(self, app):
        svc.process_return("ORD-001", "defective", is_test=True)
        goto(app, "Dashboard")
        assert {m.label: m.value for m in app.metric}["Requests processed"] == "0"
        app.toggle(key="dash_include_tests").set_value(True).run()
        assert {m.label: m.value for m in app.metric}["Requests processed"] == "1"

    def test_history_lists_and_filters_persisted_requests(self, app):
        a = svc.process_return("ORD-001", "defective")["request_id"]
        svc.process_return("ORD-002", "changed_mind")
        goto(app, "Request History")
        assert len(app.dataframe[0].value) == 2
        app.text_input(key="hist_q").set_value("ORD-001").run()
        frame = app.dataframe[0].value
        assert list(frame["Request ID"]) == [a]


class TestNoMisleadingStatus:
    def test_no_page_claims_a_refund_was_paid(self, app):
        svc.process_return("ORD-001", "defective")
        svc.process_return("ORD-011", "defective")
        for page in PAGES:
            if page in ("Agent Workflow", "Final Resolution"):
                app.session_state["selected_request"] = repo.search_requests()[0]["request_id"]
            goto(app, page)
            text = all_text(app).lower()
            # remove the explicit NEGATIVE disclaimers, then no positive claim may remain
            for disclaimer in ("no refund has been paid", "no payments are made", "no payment has been made",
                               "no payments are made and no customers", "no money is moved"):
                text = text.replace(disclaimer, "")
            for banned in ("refunded", "payment completed", "payment complete", "payment successful", "paid"):
                assert banned not in text, (page, banned)


class TestDemoPage:
    def test_run_all_marks_pass_only_from_checks(self, app):
        goto(app, "Demo and Testing")
        app.button(key="demo_all").click().run()
        text = all_text(app)
        assert "12 of 12 executed scenarios passed" in text
        assert repo.count_requests() == 11                       # SC-06 writes nothing
