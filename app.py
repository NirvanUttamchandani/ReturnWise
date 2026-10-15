"""
ReturnWise - Streamlit interface (presentation only)
====================================================
Run with:  streamlit run app.py

app.py does three things: set up the page, draw the sidebar navigation, and
call the page module for the selected section. All business operations live in
services/ and workflow.py; the database is the single source of truth, and
session state keeps only UI selections (current page, selected request id).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging

import streamlit as st

import config
from database.db import init_db
from ui import theme, common, dashboard, new_request, workflow_page, resolution, history, demo

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

st.set_page_config(page_title="ReturnWise", page_icon=":material/undo:", layout="wide",
                   initial_sidebar_state="expanded")


@st.cache_resource
def _bootstrap(db_path: str) -> bool:
    """Create/migrate the database once per server process and database file (idempotent)."""
    init_db()
    return True


_bootstrap(config.DB_PATH)
theme.inject()

PAGE_RENDERERS = {
    "Dashboard": dashboard.render,
    "New Return Request": new_request.render,
    "Agent Workflow": workflow_page.render,
    "Final Resolution": resolution.render,
    "Request History": history.render,
    "Demo and Testing": demo.render,
}

st.session_state.setdefault("page", "Dashboard")

with st.sidebar:
    st.markdown('<div class="brand">Return<span>Wise</span></div>'
                '<div class="tagline">Return and refund resolution control center</div>',
                unsafe_allow_html=True)
    for name, icon in common.PAGES:
        active = st.session_state["page"] == name
        if st.button(name, key=f"nav_{name}", icon=icon, width="stretch",
                     type="primary" if active else "secondary"):
            st.session_state["page"] = name
            st.rerun()
    st.divider()
    st.markdown(
        f'<div class="foot">Reference date (pinned): <b>{theme.esc(config.REFERENCE_DATE_STR)}</b><br>'
        "Recommendations only. No payments are made and no customers are notified.<br>"
        f"Fictional store policies &middot; v{theme.esc(config.APP_VERSION)}</div>",
        unsafe_allow_html=True)

PAGE_RENDERERS[st.session_state["page"]]()
