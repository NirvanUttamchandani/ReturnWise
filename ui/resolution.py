"""Final Resolution page: the validated (or escalated) recommendation for one request."""

import pandas as pd
import streamlit as st

import services.presentation as pres
import services.request_service as svc
from ui import theme
from ui.common import pick_request, go


def _step_output(logs: list[dict], step_types: tuple, last: bool = True) -> dict:
    rows = [l for l in logs if l["step_type"] in step_types and l.get("output")]
    if not rows:
        return {}
    return (rows[-1] if last else rows[0])["output"]


def render() -> None:
    theme.page_header("Final Resolution", "The recommendation for one request, with its evidence and validation.")
    request_id = pick_request("res")
    if not request_id:
        return
    detail = svc.get_request_detail(request_id)
    req, rec, logs = detail["request"], detail["recommendation"], detail["agent_logs"]
    if not req:
        st.error("This request no longer exists in the database.")
        return
    o = pres.outcome(req, rec)

    # Banner: label comes from stored status; never says refunded / paid.
    sub = "Recommendation only. No refund has been paid and no customer has been notified."
    st.markdown(f'<div class="banner {o["tone"]}"><h2>{theme.esc(o["label"])}</h2><p>{theme.esc(sub)}</p></div>',
                unsafe_allow_html=True)

    research = next((l["output"] for l in logs if l["agent_name"].startswith("Order and Policy") and l.get("output")), {})
    policy = research.get("policy") or {}
    order = research.get("order") or {}

    cols = st.columns(4)
    cols[0].markdown(theme.kv("Request ID", req["request_id"]), unsafe_allow_html=True)
    cols[1].markdown(theme.kv("Order ID", req["order_id"]), unsafe_allow_html=True)
    cols[2].markdown(theme.kv("Eligibility decision",
                              (rec or {}).get("eligibility_status", "—").replace("_", " ").title() if rec else "—"),
                     unsafe_allow_html=True)
    cols[3].markdown(theme.kv("Recommended action", pres.action_label((rec or {}).get("recommended_action"))),
                     unsafe_allow_html=True)
    st.write("")
    cols = st.columns(4)
    cols[0].markdown(theme.kv("Recommended refund amount", pres.money((rec or {}).get("refund_amount"))),
                     unsafe_allow_html=True)
    cols[1].markdown(theme.kv("Applicable policy", policy.get("policy_id", "—")), unsafe_allow_html=True)
    cols[2].markdown(theme.kv("Product", order.get("product_name", "—")), unsafe_allow_html=True)
    cols[3].markdown(theme.kv("Critic validation", pres.validation_label((rec or {}).get("validation_status"))),
                     unsafe_allow_html=True)
    st.write("")

    if req["status"] == "failed":
        st.error(req.get("error_message") or "Processing failed.")
        st.caption("No recommendation exists for this request. See the agent workflow for the skipped steps.")
    if not rec:
        if st.button("Open agent workflow", key="res_wf_empty", icon=":material/account_tree:"):
            go("Agent Workflow", request_id)
        return

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Why")
        st.write(rec.get("policy_explanation") or "—")
        if policy.get("notes"):
            st.caption(f"Policy {policy.get('policy_id')} (fictional): {policy['notes']}")
        resolution = next((l["output"] for l in reversed(logs)
                           if l["agent_name"].startswith("Resolution") and l.get("output")), {})
        evidence = resolution.get("supporting_evidence") or research.get("evidence") or []
        st.subheader("Evidence")
        if evidence:
            for e in evidence:
                st.markdown(f"- {e}")
        else:
            st.caption("No evidence stored for this request.")
    with right:
        st.subheader("Critic Agent validation")
        final_val = next((l["output"] for l in reversed(logs)
                          if l["step_type"] in ("validation", "revalidation") and l.get("output")), {})
        checks = final_val.get("checks_performed") or []
        if checks:
            st.dataframe(pd.DataFrame([{"Result": "Pass" if c["passed"] else "Fail", "Check": c["check"],
                                        "Detail": c["detail"]} for c in checks]),
                         hide_index=True, width="stretch")
        else:
            st.caption("No validation checks were stored for this request.")

        first_val = _step_output(logs, ("validation",))
        if rec.get("correction_attempted"):
            st.subheader("Errors and correction")
            if first_val.get("detected_errors"):
                st.error("Detected in the first recommendation: " + " | ".join(first_val["detected_errors"]))
            if rec.get("correction_details"):
                st.warning(rec["correction_details"])
        if rec["validation_status"] == "manual_review" or req["status"] == "manual_review":
            st.markdown('<div class="rw-note warn"><strong>Manual review required.</strong> '
                        'A human reviewer must decide this request before any action is taken. '
                        'ReturnWise has not approved anything.</div>', unsafe_allow_html=True)
