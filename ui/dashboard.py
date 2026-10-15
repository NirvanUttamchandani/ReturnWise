"""Dashboard page: counts from persisted rows, filters, recent requests."""

import streamlit as st

import services.reporting_service as rep
from ui import theme
from ui.common import go, request_table

STATUS_FILTER = {"": "All results", "validated": "Recommendation validated",
                 "manual_review": "Manual review required", "failed": "Processing failed"}
ACTION_FILTER = {"": "All actions", "refund": "Refund recommended", "replacement": "Replacement recommended",
                 "reject": "Rejection recommended", "manual_review": "Manual review"}


def render() -> None:
    theme.page_header("Dashboard", "Live counts computed from the SQLite database.")
    theme.note("ReturnWise produces recommendations only. A \"refund recommended\" result is NOT a refund "
               "transaction: no money is moved and no customer is notified.")

    include_tests = st.toggle("Include demo/test runs in the numbers", value=False, key="dash_include_tests")
    m = rep.get_dashboard_metrics(include_tests=include_tests)

    c = st.columns(4)
    c[0].metric("Requests processed", m["total"])
    c[1].metric("Eligible (validated)", m["eligible"])
    c[2].metric("Refund recommended", m["refund_recommended"])
    c[3].metric("Replacement recommended", m["replacement_recommended"])
    c = st.columns(4)
    c[0].metric("Rejection recommended", m["rejected"])
    c[1].metric("Manual review", m["manual_review"])
    c[2].metric("Validation failures", m["validation_failures"],
                help="Requests where the Critic Agent rejected the first recommendation.")
    c[3].metric("Correction attempts", m["correction_attempts"],
                help="Requests where one correction was attempted (maximum is one).")
    if m["processing_failed"]:
        st.caption(f"{m['processing_failed']} request(s) ended as Processing Failed (e.g. unknown order) "
                   "and are counted in the total only.")

    st.subheader("Recent requests")
    f1, f2, f3 = st.columns([2, 2, 2])
    query = f1.text_input("Search request or order ID", key="dash_q", placeholder="e.g. ORD-001")
    status = f2.selectbox("Result", list(STATUS_FILTER), format_func=STATUS_FILTER.get, key="dash_status")
    action = f3.selectbox("Action", list(ACTION_FILTER), format_func=ACTION_FILTER.get, key="dash_action")

    rows = rep.search_requests(query, status, action, include_tests, limit=15)
    selected = request_table(rows, "dash_table")
    if selected:
        st.session_state["selected_request"] = selected
        b1, b2, _ = st.columns([1.3, 1.3, 4])
        if b1.button("Open agent workflow", key="dash_open_wf", icon=":material/account_tree:"):
            go("Agent Workflow", selected)
        if b2.button("Open final resolution", key="dash_open_res", icon=":material/fact_check:"):
            go("Final Resolution", selected)
    elif rows:
        st.caption("Select a row to open its workflow or final resolution.")
