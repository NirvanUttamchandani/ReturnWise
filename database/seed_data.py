"""
ReturnWise Seed Data
Populates the database with reproducible synthetic records.

All names, email addresses, and order identifiers are entirely fictional.
Reference date: 2025-02-15  (pinned in config.REFERENCE_DATE_STR)

Scenario mapping
----------------
ORD-001  → Scenario 1  : Eligible return within window (electronics, 10 days after delivery)
ORD-002  → Scenario 2  : Expired return window       (clothing, delivered 70 days ago)
ORD-003  → Scenario 3  : Damaged product within window (furniture, 5 days after delivery)
ORD-004  → Scenario 4  : Missing order ID            (handled in workflow, no order needed)
ORD-005  → Scenario 5  : Unknown order ID            (FAKE-999, no DB row)
ORD-006  → Scenario 6  : Restricted category         (digital good, non-returnable)
ORD-007  → Scenario 7  : Order not yet delivered     (status = processing)
ORD-008  → Scenario 8  : Already returned order      (status = returned)
ORD-009  → Scenario 9  : Incorrect refund amount     (used by Critic Agent test)
ORD-010  → Scenario 10 : Intentionally invalid recommendation (Critic must catch)
ORD-011  → Scenario 11 : Valid replacement recommendation (health_safety)
ORD-012  → Scenario 12 : Ambiguous case / manual review (reason = other)
ORD-013  → Extra        : Books – eligible within 30-day window
ORD-014  → Extra        : Sports – changed-mind within window
ORD-015  → Extra        : Appliances – defective within window
ORD-016  → Extra        : Toys – expired window
ORD-017  → Extra        : Perishable – non-returnable
ORD-018  → Extra        : Clothing – wrong item within window
ORD-019  → Extra        : Electronics – cancelled order
ORD-020  → Extra        : Furniture – outside 14-day window
"""

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static datasets  (deterministic – never randomised at runtime)
# ---------------------------------------------------------------------------

CUSTOMERS = [
    ("CUST-001", "Alice Fontaine",     "alice.fontaine@example-mail.test"),
    ("CUST-002", "Brian Holloway",     "b.holloway@example-mail.test"),
    ("CUST-003", "Clara Mendes",       "clara.mendes@example-mail.test"),
    ("CUST-004", "David Okafor",       "david.okafor@example-mail.test"),
    ("CUST-005", "Elena Vasquez",      "e.vasquez@example-mail.test"),
    ("CUST-006", "Farhan Chaudhry",    "farhan.c@example-mail.test"),
    ("CUST-007", "Grace Lin",          "grace.lin@example-mail.test"),
    ("CUST-008", "Haruto Nakamura",    "h.nakamura@example-mail.test"),
    ("CUST-009", "Isabelle Dupont",    "i.dupont@example-mail.test"),
    ("CUST-010", "James Osei",         "james.osei@example-mail.test"),
]

PRODUCTS = [
    # product_id, name, category, unit_price, returnable, return_window_days
    ("PROD-001", "UltraVision 55 TV",          "electronics",    45999.00, 1, 30),
    ("PROD-002", "Men's Running Jacket",        "clothing",       2499.00,  1, 60),
    ("PROD-003", "ErgoDesk Office Chair",       "furniture",      12999.00, 1, 14),
    ("PROD-004", "CloudOS Pro License",         "digital",        3999.00,  0,  0),
    ("PROD-005", "Spark Wireless Earbuds",      "electronics",    4999.00,  1, 30),
    ("PROD-006", "Yoga Mat Premium",            "sports",         1299.00,  1, 30),
    ("PROD-007", "MedSafe Pulse Oximeter",      "health_safety",  2199.00,  1, 30),
    ("PROD-008", "Children's LEGO Set 1000pcs", "toys",           3499.00,  1, 30),
    ("PROD-009", "Python Cookbook 4th Ed",      "books",          899.00,   1, 30),
    ("PROD-010", "Organic Honey 500g",          "perishable",     349.00,   0,  0),
    ("PROD-011", "Smart Washing Machine",       "appliances",     32999.00, 1, 30),
    ("PROD-012", "Trail Running Shoes",         "sports",         5499.00,  1, 30),
    ("PROD-013", "Women's Winter Coat",         "clothing",       6999.00,  1, 60),
    ("PROD-014", "Mini Refrigerator 100L",      "appliances",     18500.00, 1, 30),
    ("PROD-015", "Bamboo Bookshelf",            "furniture",      8499.00,  1, 14),
]

POLICIES = [
    # policy_id, category, return_window_days, returnable, replacement_only, damaged_allowed, notes
    ("POL-ELEC-001", "electronics",     30, 1, 0, 1, "Standard 30-day return for all electronics."),
    ("POL-CLTH-002", "clothing",        60, 1, 0, 1, "60-day return window for clothing."),
    ("POL-FURN-004", "furniture",       14, 1, 0, 1, "Short 14-day window for furniture logistics."),
    ("POL-DIGI-007", "digital",          0, 0, 0, 0, "Non-returnable: digital goods."),
    ("POL-SPRT-010", "sports",          30, 1, 0, 1, "30-day return for sports equipment."),
    ("POL-HLTH-006", "health_safety",   30, 1, 1, 1, "Replacement only for health/safety items."),
    ("POL-TOYS-005", "toys",            30, 1, 0, 1, "30-day return for toys."),
    ("POL-BOOK-003", "books",           30, 1, 0, 1, "30-day return for books."),
    ("POL-PERI-008", "perishable",       0, 0, 0, 0, "Non-returnable: perishable goods."),
    ("POL-APPL-011", "appliances",      30, 1, 0, 1, "30-day return for appliances."),
    ("POL-INTM-009", "intimate_apparel", 0, 0, 0, 0, "Non-returnable: intimate apparel."),
]

# Orders: order_id, customer_id, product_id, quantity, unit_price, total_amount,
#         order_date, delivery_date (or None), status
ORDERS = [
    # Scenario 1: Eligible – electronics delivered 10 days before ref date (2025-02-05)
    ("ORD-001", "CUST-001", "PROD-001", 1, 45999.00, 45999.00, "2025-01-20", "2025-02-05", "delivered"),

    # Scenario 2: Expired – clothing delivered 70 days before ref date (2024-12-07) – 60-day window
    ("ORD-002", "CUST-002", "PROD-002", 1,  2499.00,  2499.00, "2024-11-25", "2024-12-07", "delivered"),

    # Scenario 3: Damaged furniture – delivered 5 days before ref date (2025-02-10) – 14-day window
    ("ORD-003", "CUST-003", "PROD-003", 1, 12999.00, 12999.00, "2025-01-28", "2025-02-10", "delivered"),

    # Scenario 4: No order ID – handled in workflow input validation (no order row needed)

    # Scenario 5: Unknown order ID – deliberate missing row (FAKE-999 referenced in test)

    # Scenario 6: Restricted – digital good delivered 2 days before ref date
    ("ORD-006", "CUST-004", "PROD-004", 1,  3999.00,  3999.00, "2025-02-10", "2025-02-13", "delivered"),

    # Scenario 7: Not delivered – status = processing
    ("ORD-007", "CUST-005", "PROD-005", 1,  4999.00,  4999.00, "2025-02-10", None,         "processing"),

    # Scenario 8: Already returned
    ("ORD-008", "CUST-006", "PROD-006", 1,  1299.00,  1299.00, "2025-01-01", "2025-01-10", "returned"),

    # Scenario 9: Electronics – used in incorrect-refund-amount test
    ("ORD-009", "CUST-007", "PROD-005", 2,  4999.00,  9998.00, "2025-01-15", "2025-01-25", "delivered"),

    # Scenario 10: Electronics – Critic must catch intentionally invalid recommendation
    ("ORD-010", "CUST-008", "PROD-001", 1, 45999.00, 45999.00, "2025-01-10", "2025-01-20", "delivered"),

    # Scenario 11: Health/safety – replacement only
    ("ORD-011", "CUST-009", "PROD-007", 1,  2199.00,  2199.00, "2025-01-28", "2025-02-05", "delivered"),

    # Scenario 12: Ambiguous – reason = other → manual review
    ("ORD-012", "CUST-010", "PROD-009", 1,   899.00,   899.00, "2025-01-20", "2025-02-01", "delivered"),

    # Extra orders for a fuller dataset
    ("ORD-013", "CUST-001", "PROD-009", 2,   899.00,  1798.00, "2025-01-25", "2025-02-03", "delivered"),
    ("ORD-014", "CUST-002", "PROD-006", 1,  1299.00,  1299.00, "2025-01-28", "2025-02-08", "delivered"),
    ("ORD-015", "CUST-003", "PROD-011", 1, 32999.00, 32999.00, "2025-01-15", "2025-01-28", "delivered"),
    ("ORD-016", "CUST-004", "PROD-008", 1,  3499.00,  3499.00, "2024-12-01", "2024-12-10", "delivered"),
    ("ORD-017", "CUST-005", "PROD-010", 2,   349.00,   698.00, "2025-02-12", "2025-02-14", "delivered"),
    ("ORD-018", "CUST-006", "PROD-013", 1,  6999.00,  6999.00, "2025-01-20", "2025-01-30", "delivered"),
    ("ORD-019", "CUST-007", "PROD-001", 1, 45999.00, 45999.00, "2025-02-01", None,         "cancelled"),
    ("ORD-020", "CUST-008", "PROD-015", 1,  8499.00,  8499.00, "2025-01-01", "2025-01-05", "delivered"),

    # Extra: ORD-021 – Clothing within 60-day window
    ("ORD-021", "CUST-009", "PROD-013", 1,  6999.00,  6999.00, "2025-01-10", "2025-01-20", "delivered"),

    # Extra: ORD-022 – Appliances expired 30-day window (delivered 52 days ago)
    ("ORD-022", "CUST-010", "PROD-014", 1, 18500.00, 18500.00, "2024-12-15", "2024-12-25", "delivered"),
]



def seed_all() -> None:
    """Insert all seed records if tables are empty. Idempotent."""
    from database.db import get_connection

    conn = get_connection()
    try:
        with conn:
            _seed_customers(conn)
            _seed_products(conn)
            _seed_policies(conn)
            _seed_orders(conn)
        logger.info("Seed data applied.")
    finally:
        conn.close()


def _seed_customers(conn) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    if existing:
        return
    conn.executemany(
        "INSERT INTO customers (customer_id, name, email) VALUES (?, ?, ?)",
        CUSTOMERS,
    )


def _seed_products(conn) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if existing:
        return
    conn.executemany(
        """INSERT INTO products
           (product_id, name, category, unit_price, returnable, return_window_days)
           VALUES (?, ?, ?, ?, ?, ?)""",
        PRODUCTS,
    )


def _seed_policies(conn) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM return_policies").fetchone()[0]
    if existing:
        return
    conn.executemany(
        """INSERT INTO return_policies
           (policy_id, category, return_window_days, returnable,
            replacement_only, damaged_allowed, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        POLICIES,
    )


def _seed_orders(conn) -> None:
    existing = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    if existing:
        return
    conn.executemany(
        """INSERT INTO orders
           (order_id, customer_id, product_id, quantity, unit_price,
            total_amount, order_date, delivery_date, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ORDERS,
    )
