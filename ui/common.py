"""Shared UI helpers: navigation, request picker and the selectable request table.

Session state holds only UI selections (current page, selected request id).
Every page re-reads the selected request from the database on each render.
"""

import pandas as pd
import streamlit as st

import services.presentation as pres
import services.reporting_service as rep

PAGES = [
    ("Dashboard",            ":material/dashboard:"),
    ("New Return Request",   ":material/add_box:"),
    ("Agent Workflow",       ":material/account_tree:"),
    ("Final Resolution",     ":material/fact_check:"),
    ("Request History",      ":material/history:"),
    ("Demo and Testing",     ":material/science:"),
]


def go(page: str, request_id: str | None = None) -> None:
    """Switch page (optionally selecting a request) and rerun."""
    st.session_state["page"] = page
    if request_id:
        st.session_state["selected_request"] = request_id
    st.rerun()


def request_label(row: dict) -> str:
    o = pres.outcome({"status": row["status"]},
                     {"recommended_action": row.get("recommended_action"),
                      "validation_status": row.get("validation_status")} if row.get("recommended_action") else None)
    return f'{row["request_id"]}  |  {row["order_id"]}  |  {o["label"]}' + ("  [test]" if row.get("is_test") else "")


def pick_request(key: str) -> str | None:
    """Selectbox of stored requests; returns the chosen request id (or None if there are none)."""
    rows = rep.search_requests(limit=100)
    if not rows:
        st.info("No requests have been processed yet.")
        if st.button("Create a return request", key=f"{key}_empty", icon=":material/add_box:"):
            go("New Return Request")
        return None
    ids = [r["request_id"] for r in rows]
    current = st.session_state.get("selected_request")
    index = ids.index(current) if current in ids else 0
    chosen = st.selectbox(
        "Request", ids, index=index, key=f"{key}_pick",
        format_func=lambda rid: request_label(rows[ids.index(rid)]),
    )
    st.session_state["selected_request"] = chosen
    return chosen


def rows_to_frame(rows: list[dict]) -> pd.DataFrame:
    out = []
    for r in rows:
        rec = ({"recommended_action": r.get("recommended_action"),
                "validation_status": r.get("validation_status")} if r.get("recommended_action") else None)
        o = pres.outcome({"status": r["status"]}, rec)
        out.append({
            "Request ID": r["request_id"],
            "Order ID": r["order_id"],
            "Submitted (UTC)": (r["submitted_at"] or "")[:16].replace("T", " "),
            "Reason": (r["reason"] or "").replace("_", " ").title(),
            "Result": o["label"],
            "Validation": pres.validation_label(r.get("validation_status")) if r.get("validation_status") else "—",
            "Recommended amount": pres.money(r.get("refund_amount")),
            "Corrected": "Yes" if r.get("correction_attempted") else "",
            "Test run": "Yes" if r.get("is_test") else "",
        })
    return pd.DataFrame(out)


def request_table(rows: list[dict], key: str) -> str | None:
    """Show a single-row-selectable table; return the selected request id."""
    if not rows:
        st.info("No requests match the current filters.")
        return None
    event = st.dataframe(
        rows_to_frame(rows), hide_index=True, width="stretch",
        on_select="rerun", selection_mode="single-row", key=key,
    )
    picked = event.selection.rows if event and event.selection else []
    if picked and picked[0] < len(rows):
        return rows[picked[0]]["request_id"]
    return None
