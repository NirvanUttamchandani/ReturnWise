"""Demo and Testing page: predefined scenarios with expected-vs-actual comparison."""

import pandas as pd
import streamlit as st

import services.demo_service as demo
from ui import theme
from ui.common import go


def _run(ids: list[str]) -> None:
    results = st.session_state.setdefault("demo_results", {})
    for sc in demo.get_scenarios():
        if sc["id"] in ids:
            results[sc["id"]] = demo.run_scenario(sc)


def render() -> None:
    theme.page_header("Demo and Testing", "Predefined synthetic scenarios, checked against what the database stored.")
    theme.note("TEST MODE. Scenarios run the real workflow, but their requests are saved with a TEST flag and "
               "are left out of the dashboard numbers by default. A scenario passes only if every expected "
               "value matches the stored result; clicking Run does not count as a pass.", "warn")

    scenarios = demo.get_scenarios()
    results = st.session_state.get("demo_results", {})

    top = st.columns([1.4, 4])
    if top[0].button("Run all scenarios", type="primary", key="demo_all", icon=":material/play_arrow:"):
        _run([s["id"] for s in scenarios])
        st.rerun()
    if results:
        passed = sum(1 for r in results.values() if r["passed"])
        top[1].markdown(f"**{passed} of {len(results)} executed scenarios passed** "
                        f"({len(scenarios) - len(results)} not run yet)")

    for sc in scenarios:
        res = results.get(sc["id"])
        with st.container(border=True):
            h1, h2, h3 = st.columns([5, 1.6, 1.2])
            h1.markdown(f"**{sc['id']}** &nbsp; {theme.esc(sc['title'])}", unsafe_allow_html=True)
            meta = f"Order `{sc['order_id'] or '(blank)'}` | reason `{sc['reason']}`"
            if sc.get("fault"):
                meta += f" | injected fault `{sc['fault']}`"
            h1.caption(meta)
            if res is None:
                h2.markdown(theme.badge("Not run", "muted"), unsafe_allow_html=True)
            else:
                h2.markdown(theme.badge("Passed" if res["passed"] else "Failed", "ok" if res["passed"] else "bad"),
                            unsafe_allow_html=True)
            if h3.button("Run", key=f"demo_run_{sc['id']}", icon=":material/play_arrow:"):
                _run([sc["id"]])
                st.rerun()
            if res:
                frame = pd.DataFrame([{"Check": c["check"], "Expected": str(c["expected"]),
                                       "Actual": str(c["actual"]), "Result": "Pass" if c["passed"] else "Fail"}
                                      for c in res["checks"]])
                st.dataframe(frame, hide_index=True, width="stretch")
                if res.get("request_id"):
                    if st.button("Open workflow for " + res["request_id"], key=f"demo_open_{sc['id']}",
                                 icon=":material/account_tree:"):
                        go("Agent Workflow", res["request_id"])
