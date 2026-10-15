"""Agent timeline renderer shared by the Agent Workflow and Request History pages.

It draws ONLY stored agent_logs rows (one row = one real execution record,
including SKIPPED rows). Nothing is invented.
"""

import pandas as pd
import streamlit as st

from ui import theme

STEP_TITLES = {1: "Intake and Planning", 2: "Order and Policy Research", 3: "Eligibility Evaluation",
               4: "Resolution", 5: "Validation", 6: "Resolution (correction pass)", 7: "Validation (revalidation)"}


def _status_badge(log: dict) -> tuple[str, str]:
    """(text, tone) for the execution status of a step."""
    if log["status"] == "skipped":
        return "Skipped", "muted"
    if log["status"] == "error":
        return "Failed", "bad"
    return "Completed", "ok"


def _verdict_badge(log: dict) -> tuple[str, str] | None:
    v, t = log.get("verdict"), log["step_type"]
    if log["status"] != "success" or not v:
        return None
    if t in ("validation", "revalidation"):
        return {"passed": ("Recommendation validated", "ok"),
                "failed": ("Recommendation rejected by Critic", "bad"),
                "manual_review": ("Escalated to manual review", "warn")}.get(v)
    if log["agent_name"].startswith("Eligibility"):
        return {"eligible": ("Eligible", "ok"), "ineligible": ("Ineligible", "bad"),
                "manual_review": ("Manual review", "warn")}.get(v)
    if log["agent_name"].startswith("Resolution"):
        return {"refund": ("Proposes refund", "info"), "replacement": ("Proposes replacement", "info"),
                "reject": ("Proposes rejection", "info"), "manual_review": ("Proposes manual review", "warn")}.get(v)
    return None


def render(logs: list[dict], key: str) -> None:
    if not logs:
        st.info("No agent execution records are stored for this request.")
        return
    shown_loop_note = False
    for log in logs:
        order = log["execution_order"]
        if order == 6 and not shown_loop_note:
            _correction_banner(logs)
            shown_loop_note = True
        _step(log, key)


def _correction_banner(logs: list[dict]) -> None:
    first = next((l for l in logs if l["step_type"] == "validation"), None)
    reval = next((l for l in logs if l["step_type"] == "revalidation"), None)
    out = (first or {}).get("output") or {}
    msg = ("Correction loop: the Critic Agent rejected the first recommendation "
           f"({' | '.join(e.rstrip('.') for e in out.get('detected_errors', [])) or 'see step 5'}). "
           "One correction was applied by the Resolution Agent and the Critic revalidated it.")
    if reval and reval.get("verdict") == "passed":
        msg += " Revalidation passed."
        theme.note(msg)
    else:
        msg += " Revalidation did not pass, so the request was escalated to manual review."
        theme.note(msg, "warn")


def _step(log: dict, key: str) -> None:
    order = log["execution_order"]
    s_text, s_tone = _status_badge(log)
    v = _verdict_badge(log)
    out = log.get("output") or {}
    summary = log.get("output_summary") or log.get("explanation") or ""
    num_tone = {"ok": "", "bad": "bad", "muted": "muted"}[s_tone]
    if log["step_type"] in ("validation", "revalidation") and log.get("verdict") == "failed":
        num_tone = "warn"
    title = log["agent_name"]
    right = theme.badge(s_text, s_tone) + (theme.badge(*v) if v else "")
    with st.container(border=True):
        st.markdown(
            f'<div class="step"><div class="step-num {num_tone}">{order}</div>'
            f'<div><div class="step-title">{theme.esc(title)}<span class="chip">{theme.esc(log["agent_role"])}</span></div>'
            f'<div class="step-sub">{theme.esc(summary[:220])}</div></div>'
            f'<div class="step-right">{right}</div></div>',
            unsafe_allow_html=True,
        )
        with st.expander("Inputs, outputs and evidence", expanded=False):
            _details(log, out, key)


def _details(log: dict, out: dict, key: str) -> None:
    if log["status"] == "skipped":
        st.info(log.get("explanation") or "This agent was skipped.")
        return
    if out.get("fault_injected"):
        st.warning(f"Test scenario: fault '{out['fault_injected']}' was deliberately injected into this "
                   "recommendation so the Critic Agent has an error to catch.")
    c1, c2 = st.columns(2)
    c1.markdown("**Input summary**")
    c1.code(log.get("input_summary") or "(none)", language=None)
    c2.markdown("**Output summary**")
    c2.code(log.get("output_summary") or "(none)", language=None)
    st.markdown("**Explanation**")
    st.write(log.get("explanation") or "—")
    if log["status"] == "error":
        st.error(log.get("explanation") or "The agent reported an error.")

    if out.get("task_plan"):
        st.markdown("**Task plan**")
        for t in out["task_plan"]:
            st.markdown(f"- {t}")
    if out.get("missing_fields"):
        st.error("Missing or invalid fields: " + ", ".join(out["missing_fields"]))
    if out.get("description_flags"):
        st.warning("The customer text contained wording that tries to influence the decision. "
                   "It was flagged and ignored; only database records and policy rules decide.")
    if out.get("evidence"):
        st.markdown("**Evidence retrieved**")
        for e in out["evidence"]:
            st.markdown(f"- {e}")
    if out.get("rule_checks"):
        st.markdown("**Policy rule checks**")
        st.dataframe(pd.DataFrame([{"Result": "Pass" if r["passed"] else "Fail", "Rule": r["rule"],
                                    "Detail": r["reason"]} for r in out["rule_checks"]]),
                     hide_index=True, width="stretch")
    if out.get("checks_performed"):
        st.markdown("**Critic checks**")
        st.dataframe(pd.DataFrame([{"Result": "Pass" if c["passed"] else "Fail", "Check": c["check"],
                                    "Detail": c["detail"]} for c in out["checks_performed"]]),
                     hide_index=True, width="stretch")
    if out.get("detected_errors"):
        st.error("Detected errors: " + " | ".join(out["detected_errors"]))
    if out.get("correction_details"):
        st.warning("Correction requested: " + out["correction_details"])
    st.markdown("**Structured output**")
    st.json(out if out else {"note": "No structured output stored for this legacy record."}, expanded=False)
