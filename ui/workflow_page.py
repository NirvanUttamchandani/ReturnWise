"""Agent Workflow page: the stored execution timeline of one request."""

import streamlit as st

import services.presentation as pres
import services.request_service as svc
from ui import theme, timeline
from ui.common import pick_request


def summary_strip(detail: dict) -> None:
    req, rec = detail["request"], detail["recommendation"]
    o = pres.outcome(req, rec)
    cols = st.columns(4)
    cols[0].markdown(theme.kv("Request ID", req["request_id"]), unsafe_allow_html=True)
    cols[1].markdown(theme.kv("Order ID", req["order_id"]), unsafe_allow_html=True)
    cols[2].markdown(theme.kv("Reason", (req["reason"] or "").replace("_", " ").title()), unsafe_allow_html=True)
    cols[3].markdown(theme.kv("Result", o["label"]), unsafe_allow_html=True)


def render() -> None:
    theme.page_header("Agent Workflow",
                      "Every step below is a stored execution record for the selected request.")
    request_id = pick_request("wf")
    if not request_id:
        return
    detail = svc.get_request_detail(request_id)       # fresh read, never cached in session state
    if not detail["request"]:
        st.error("This request no longer exists in the database.")
        return
    summary_strip(detail)
    st.write("")
    if detail["request"]["is_test"]:
        theme.note("This request was created by a Demo and Testing scenario (marked TEST).", "warn")
    timeline.render(detail["agent_logs"], key="wf")
