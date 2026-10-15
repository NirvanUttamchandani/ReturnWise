"""New Return Request page: validated form, duplicate-safe submit, backend-returned request ID."""

import uuid
import streamlit as st

import services.presentation as pres
import services.reporting_service as rep
import services.request_service as svc
from ui import theme
from ui.common import go

REASONS = {
    "defective": "Defective / not working",
    "wrong_item": "Wrong item received",
    "damaged": "Arrived damaged",
    "changed_mind": "Changed my mind",
    "other": "Other (needs manual review)",
}


def _apply_sample() -> None:
    """Callback: copy the chosen sample order into the order-ID box."""
    choice = st.session_state.get("nr_sample", "")
    if choice:
        st.session_state["nr_order"] = choice.split(" ")[0]


def render() -> None:
    theme.page_header("New Return Request",
                      "Submit a return; five agents analyse it and produce a validated recommendation.")
    # One token per form 'session': a double click or rerun can never create a second request.
    st.session_state.setdefault("nr_token", uuid.uuid4().hex)

    orders = rep.get_all_orders()
    sample_labels = [f'{o["order_id"]}  -  {o["product_name"]} ({o["status"]})' for o in orders]

    left, right = st.columns([3, 2], gap="large")
    with left:
        with st.container(border=True):
            st.selectbox("Sample order (optional)", [""] + sample_labels, key="nr_sample",
                         on_change=_apply_sample, format_func=lambda x: x or "Choose a sample order...",
                         help="Fills the Order ID box from the synthetic dataset.")
            order_id = st.text_input("Order ID *", key="nr_order", placeholder="e.g. ORD-001", max_chars=32)
            reason = st.selectbox("Return reason *", list(REASONS), format_func=REASONS.get, key="nr_reason")
            description = st.text_area("Additional details (optional)", key="nr_desc", max_chars=500,
                                       placeholder="Describe the issue. This text is stored but never changes the decision.")
            submit = st.button("Submit return request", type="primary", key="nr_submit",
                               icon=":material/send:")

        if submit:
            _, error = svc.validate_request_input(order_id, reason, description)
            if error:
                st.error(error)
            else:
                with st.status("Processing through the five agents...", expanded=False) as status:
                    result = svc.process_return(order_id, reason, description,
                                                client_token=st.session_state["nr_token"])
                    status.update(label="Processing finished", state="complete")
                if result["request_id"]:
                    st.session_state["nr_last"] = result["request_id"]
                    st.session_state["selected_request"] = result["request_id"]
                    if not result["duplicate"]:
                        st.session_state["nr_token"] = uuid.uuid4().hex  # next submission is a new request
                if result["duplicate"]:
                    st.warning("This submission was already processed; no duplicate request was created.")
                if not result["request_id"]:
                    st.error(result["error"] or "The request could not be processed.")

        _show_last_result()

    with right:
        with st.container(border=True):
            st.markdown("**How it works**")
            st.markdown(
                "1. **Intake** checks the fields and plans the work\n"
                "2. **Research** loads the order and policy from the database\n"
                "3. **Eligibility** applies the policy rules in Python\n"
                "4. **Resolution** recommends refund, replacement, rejection or manual review\n"
                "5. **Validation (Critic)** re-checks it, and may request one correction"
            )
            st.caption("Store policies are fictional and exist only for this proof of concept.")


def _show_last_result() -> None:
    request_id = st.session_state.get("nr_last")
    if not request_id:
        return
    detail = svc.get_request_detail(request_id)      # always re-read from the database
    req, rec = detail["request"], detail["recommendation"]
    if not req:
        return
    o = pres.outcome(req, rec)
    st.markdown("---")
    st.markdown(f"**Request ID:** `{req['request_id']}` &nbsp; {theme.badge(o['label'], o['tone'])}",
                unsafe_allow_html=True)
    if req["status"] == "failed":
        st.error(req.get("error_message") or "Processing failed.")
    elif rec:
        amt = f" Recommended refund amount: {pres.money(rec['refund_amount'])}." if rec["refund_amount"] else ""
        st.success(f"Saved. Order {rec['order_id']}: {pres.action_label(rec['recommended_action'])}.{amt} "
                   "No payment has been made.")
    b1, b2, _ = st.columns([1.3, 1.3, 4])
    if b1.button("View agent workflow", key="nr_view_wf", icon=":material/account_tree:"):
        go("Agent Workflow", request_id)
    if b2.button("View final resolution", key="nr_view_res", icon=":material/fact_check:"):
        go("Final Resolution", request_id)
