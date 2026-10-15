"""Request History page: search, filter, and open any stored request with its full timeline."""

import streamlit as st

import services.presentation as pres
import services.reporting_service as rep
import services.request_service as svc
from ui import theme, timeline
from ui.common import request_table, go
from ui.dashboard import STATUS_FILTER, ACTION_FILTER
from ui.workflow_page import summary_strip


def render() -> None:
    theme.page_header("Request History", "Every request is read from the database, including its agent timeline.")
    f1, f2, f3, f4 = st.columns([2.2, 2, 2, 1.6])
    query = f1.text_input("Search request or order ID", key="hist_q", placeholder="REQ-... or ORD-...")
    status = f2.selectbox("Result", list(STATUS_FILTER), format_func=STATUS_FILTER.get, key="hist_status")
    action = f3.selectbox("Recommended action", list(ACTION_FILTER), format_func=ACTION_FILTER.get, key="hist_action")
    include_tests = f4.toggle("Include test runs", value=True, key="hist_tests")

    rows = rep.search_requests(query, status, action, include_tests, limit=200)
    st.caption(f"{len(rows)} request(s)")
    selected = request_table(rows, "hist_table")
    if not selected:
        if rows:
            st.caption("Select a row to see the full detail and agent timeline.")
        return

    st.session_state["selected_request"] = selected
    detail = svc.get_request_detail(selected)        # fetched for exactly this request id
    if not detail["request"]:
        st.error("Request not found.")
        return
    st.divider()
    st.subheader(f"Request {selected}")
    summary_strip(detail)
    req, rec = detail["request"], detail["recommendation"]
    if rec:
        st.write("")
        st.markdown(
            f"**{pres.action_label(rec['recommended_action'])}** &nbsp; "
            f"{theme.badge(pres.validation_label(rec['validation_status']), 'muted')} &nbsp; "
            f"Recommended amount: {pres.money(rec['refund_amount'])}", unsafe_allow_html=True)
    elif req["status"] == "failed":
        st.error(req.get("error_message") or "Processing failed.")
    if st.button("Open final resolution", key="hist_open_res", icon=":material/fact_check:"):
        go("Final Resolution", selected)
    st.subheader("Agent execution timeline")
    timeline.render(detail["agent_logs"], key=f"hist_{selected}")
