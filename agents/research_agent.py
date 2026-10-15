"""
Agent 2 – Order and Policy Research Agent  (Role: Research Agent)

Responsibilities:
  - Retrieve the matching order and product from the database.
  - Retrieve the applicable store policy for the product category.
  - Check delivery date, order status, and return window.
  - Return structured evidence for the Eligibility Agent.
  - Return an explicit error if the order or policy cannot be found.

Input contract:
    {
        "order_id": str,   # from Intake Agent output
        "reason":   str    # normalised reason code
    }

Output contract:
    {
        "status":          "success" | "error",
        "order":           dict | None,
        "policy":          dict | None,
        "days_since_delivery": int | None,
        "within_window":   bool | None,
        "data_issues":     list[str],     # ambiguous/inconsistent records -> manual review
        "evidence":        list[str],
        "explanation":     str,
        "input_summary":   str,
        "output_summary":  str
    }
"""

import logging

import config
import database.repository as repo
from policies import rules

logger = logging.getLogger(__name__)


def run(intake_output: dict) -> dict:
    """
    Execute the Order and Policy Research Agent.

    Parameters
    ----------
    intake_output : dict
        Output of the Intake Agent (must have status="success").

    Returns
    -------
    dict
        Structured research output (see module docstring).
    """
    order_id = intake_output.get("order_id")
    reason   = intake_output.get("reason")

    input_summary = f"order_id={order_id!r}, reason={reason!r}"

    # --- Retrieve order ---
    order = repo.get_order(order_id)
    if order is None:
        explanation = (
            f"Order '{order_id}' was not found in the database. "
            "This is either an unknown order ID or a test scenario for an unknown order. "
            "Downstream agents cannot proceed without order data."
        )
        return {
            "status":               "error",
            "order":                None,
            "policy":               None,
            "days_since_delivery":  None,
            "within_window":        None,
            "data_issues":          [],
            "evidence":             [],
            "explanation":          explanation,
            "input_summary":        input_summary,
            "output_summary":       f"Order '{order_id}' not found.",
        }

    # --- Retrieve policy ---
    category = order["category"]
    policy = repo.get_policy_by_category(category)
    if policy is None:
        explanation = (
            f"No return policy found for product category '{category}'. "
            "This is a data consistency problem, so processing stops and no decision is made. A person should check the policy data."
        )
        return {
            "status":               "error",
            "order":                order,
            "policy":               None,
            "days_since_delivery":  None,
            "within_window":        None,
            "data_issues":          [],
            "evidence":             [f"Order found: {order_id}", f"No policy for category: {category}"],
            "explanation":          explanation,
            "input_summary":        input_summary,
            "output_summary":       f"Policy not found for category '{category}'.",
        }

    # --- Calculate return window ---
    # Data-integrity problems make the case ambiguous (handled downstream as manual review).
    data_issues = rules.check_order_integrity(order)

    delivery_date_str = order.get("delivery_date")
    days_since_delivery = None
    within_window = None

    if delivery_date_str:
        try:
            days_since_delivery = rules.days_since_delivery(delivery_date_str)
            within_window = rules.is_within_window(days_since_delivery, policy["return_window_days"])
        except ValueError:
            pass  # malformed date: already reported in data_issues; window stays unknown (None)

    # --- Build evidence list ---
    evidence = [
        f"Order ID: {order_id}",
        f"Product: {order['product_name']} (category: {category})",
        f"Order status: {order['status']}",
        f"Delivery date: {delivery_date_str or 'Not delivered'}",
        f"Reference date (pinned): {config.REFERENCE_DATE_STR}",
        f"Days since delivery: {days_since_delivery}",
        f"Return window: {policy['return_window_days']} days",
        f"Within return window: {within_window}",
        f"Policy returnable: {bool(policy['returnable'])}",
        f"Policy replacement_only: {bool(policy['replacement_only'])}",
        f"Policy damaged_allowed: {bool(policy['damaged_allowed'])}",
        f"Return reason: {reason}",
    ]
    evidence += [f"DATA ISSUE: {issue}" for issue in data_issues]

    explanation = (
        f"Retrieved order '{order_id}' for product '{order['product_name']}' "
        f"(category: {category}). "
        f"Order status is '{order['status']}'. "
        + (
            f"Delivered {days_since_delivery} day(s) ago. "
            f"Return window is {policy['return_window_days']} day(s). "
            f"Currently {'within' if within_window else 'outside'} the return window. "
            if delivery_date_str else
            "Item has not been delivered yet. "
        )
        + f"Applicable policy: {policy['policy_id']}."
    )

    return {
        "status":               "success",
        "order":                dict(order),
        "policy":               dict(policy),
        "days_since_delivery":  days_since_delivery,
        "within_window":        within_window,
        "data_issues":          data_issues,
        "evidence":             evidence,
        "explanation":          explanation,
        "input_summary":        input_summary,
        "output_summary":       (
            f"Order {order_id} found. Category: {category}. "
            f"Status: {order['status']}. "
            f"Days since delivery: {days_since_delivery}. "
            f"Within window: {within_window}."
        ),
    }
