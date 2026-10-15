"""
ReturnWise shared policy helpers.

Small, pure functions used by more than one agent so the business rules are
written once:
  * return-window arithmetic (documented reference date, inclusive boundary)
  * order data-integrity checks (ambiguous / inconsistent data -> manual review)
  * loader for the human-readable JSON policy document

All store policies are FICTIONAL and exist only for this PoC.
"""

import json
import os
from datetime import date

import config

POLICY_JSON_PATH = os.path.join(os.path.dirname(__file__), "return_policy.json")


def reference_date() -> date:
    """The pinned 'today' used for every window calculation (see config)."""
    return date.fromisoformat(config.REFERENCE_DATE_STR)


def days_since_delivery(delivery_date: str, ref: date | None = None) -> int:
    """Whole days between delivery and the reference date (day 0 = delivery day)."""
    ref = ref or reference_date()
    return (ref - date.fromisoformat(delivery_date)).days


def is_within_window(days: int, window_days: int) -> bool:
    """
    Inclusive boundary: a 30-day window still accepts day 30, rejects day 31.
    A 0-day window (non-returnable category) is never open.
    A negative number of days (delivery in the future) is not a valid state.
    """
    if window_days <= 0 or days < 0:
        return False
    return days <= window_days


def check_order_integrity(order: dict) -> list[str]:
    """
    Return a list of data problems for an order joined with its product.
    Any problem means the data is ambiguous, so the request goes to manual
    review instead of receiving an invented decision.
    """
    issues: list[str] = []
    qty = order.get("quantity")
    unit = order.get("unit_price")
    total = order.get("total_amount")

    if qty is None or qty < 1:
        issues.append(f"Invalid quantity: {qty}.")
    if unit is None or unit <= 0:
        issues.append(f"Invalid unit price: {unit}.")
    if total is None or total <= 0:
        issues.append(f"Invalid order total: {total}.")
    if not issues and abs(round(qty * unit, 2) - round(total, 2)) > 0.01:
        issues.append(
            f"Order total {total} does not equal quantity x unit price ({qty} x {unit})."
        )
    product_price = order.get("product_unit_price")
    if product_price is not None and unit is not None and abs(product_price - unit) > 0.01:
        issues.append(
            f"Order unit price {unit} differs from catalogue price {product_price}."
        )

    status = order.get("status")
    delivery = order.get("delivery_date")
    if status in ("delivered", "returned") and not delivery:
        issues.append(f"Order status is '{status}' but no delivery date is recorded.")
    if status in ("pending", "processing", "cancelled") and delivery:
        issues.append(f"Order status is '{status}' but a delivery date is recorded.")
    if delivery:
        try:
            d = date.fromisoformat(delivery)
            if d > reference_date():
                issues.append("Delivery date is after the reference date.")
            if order.get("order_date") and d < date.fromisoformat(order["order_date"]):
                issues.append("Delivery date is before the order date.")
        except ValueError:
            issues.append(f"Delivery date '{delivery}' is not a valid ISO date.")
    return issues


def load_policy_document() -> dict:
    """Load the documented JSON policy (the DB table is seeded from the same values)."""
    with open(POLICY_JSON_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)
