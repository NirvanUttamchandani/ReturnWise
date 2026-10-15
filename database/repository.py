"""
ReturnWise Repository Layer
All database read/write operations in one place.
Uses parameterised queries only – no dynamic SQL from user input.
"""

import logging
from typing import Optional

from database.db import get_connection

logger = logging.getLogger(__name__)


# ============================================================
# Orders
# ============================================================

def get_order(order_id: str) -> Optional[dict]:
    """Return the order joined with its product, or None if not found."""
    sql = """
        SELECT o.order_id, o.customer_id, o.product_id, o.quantity,
               o.unit_price, o.total_amount, o.order_date, o.delivery_date,
               o.status,
               p.name AS product_name, p.category, p.returnable,
               p.unit_price AS product_unit_price,
               p.return_window_days AS product_return_window_days,
               c.name AS customer_name, c.email AS customer_email
        FROM   orders o
        JOIN   products p ON o.product_id = p.product_id
        JOIN   customers c ON o.customer_id = c.customer_id
        WHERE  o.order_id = ?
    """
    conn = get_connection()
    try:
        row = conn.execute(sql, (order_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_orders() -> list[dict]:
    sql = """
        SELECT o.order_id, o.customer_id, o.product_id, o.quantity,
               o.unit_price, o.total_amount, o.order_date, o.delivery_date,
               o.status, p.name AS product_name, p.category
        FROM   orders o
        JOIN   products p ON o.product_id = p.product_id
        ORDER  BY o.order_date DESC
    """
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


# ============================================================
# Policies
# ============================================================

def get_policy_by_category(category: str) -> Optional[dict]:
    """Return the return policy for a product category, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM return_policies WHERE category = ?", (category,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_policies() -> list[dict]:
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM return_policies").fetchall()]
    finally:
        conn.close()


# ============================================================
# Return Requests
# ============================================================

def create_return_request(
    request_id: str,
    order_id: str,
    reason: str,
    description: Optional[str],
    submitted_at: str,
    is_test: bool = False,
    client_token: Optional[str] = None,
) -> None:
    """Insert a new return request. Raises sqlite3.IntegrityError on a duplicate id/token."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """INSERT INTO return_requests
                   (request_id, order_id, reason, description, submitted_at, status,
                    is_test, client_token)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (request_id, order_id, reason, description, submitted_at,
                 1 if is_test else 0, client_token),
            )
    finally:
        conn.close()


def update_request_status(request_id: str, status: str) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE return_requests SET status = ? WHERE request_id = ?",
                (status, request_id),
            )
    finally:
        conn.close()


def get_return_request(request_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM return_requests WHERE request_id = ?", (request_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_return_requests() -> list[dict]:
    conn = get_connection()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM return_requests ORDER BY submitted_at DESC"
            ).fetchall()
        ]
    finally:
        conn.close()


# ============================================================
# Agent Logs
# ============================================================

def log_agent_execution(
    request_id: str,
    agent_name: str,
    agent_role: str,
    execution_order: int,
    status: str,
    input_summary: str,
    output_summary: str,
    explanation: str,
    executed_at: str,
    step_type: str = "agent",
    verdict: Optional[str] = None,
    input_json: Optional[str] = None,
    output_json: Optional[str] = None,
) -> None:
    """Insert one agent-log row in its own transaction (workflow uses save_workflow_result)."""
    conn = get_connection()
    try:
        with conn:
            _insert_agent_log(
                conn, request_id, agent_name, agent_role, execution_order, status,
                input_summary, output_summary, explanation, executed_at,
                step_type, verdict, input_json, output_json,
            )
    finally:
        conn.close()


def _insert_agent_log(
    conn, request_id, agent_name, agent_role, execution_order, status,
    input_summary, output_summary, explanation, executed_at,
    step_type="agent", verdict=None, input_json=None, output_json=None,
) -> None:
    conn.execute(
        """INSERT INTO agent_logs
           (request_id, agent_name, agent_role, execution_order, status,
            input_summary, output_summary, explanation, executed_at,
            step_type, verdict, input_json, output_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            request_id, agent_name, agent_role, execution_order, status,
            input_summary, output_summary, explanation, executed_at,
            step_type, verdict, input_json, output_json,
        ),
    )


def get_agent_logs(request_id: str) -> list[dict]:
    conn = get_connection()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM agent_logs WHERE request_id = ? ORDER BY execution_order",
                (request_id,),
            ).fetchall()
        ]
    finally:
        conn.close()


# ============================================================
# Atomic workflow persistence
# ============================================================

def save_workflow_result(
    request_id: str,
    steps: list[dict],
    recommendation: Optional[dict],
    request_status: str,
    error_message: Optional[str] = None,
) -> None:
    """
    Persist everything a workflow run produced in ONE transaction:
    all agent-log rows, the recommendation (if any) and the request status.
    If any statement fails, nothing is written (the `with conn` block rolls back)
    and the exception propagates so the caller can report a failure.
    """
    conn = get_connection()
    try:
        with conn:
            for st in steps:
                _insert_agent_log(
                    conn, request_id, st["agent_name"], st["agent_role"],
                    st["execution_order"], st["status"], st["input_summary"],
                    st["output_summary"], st["explanation"], st["executed_at"],
                    st["step_type"], st.get("verdict"),
                    st.get("input_json"), st.get("output_json"),
                )
            if recommendation:
                conn.execute(
                    """INSERT INTO recommendations
                       (recommendation_id, request_id, order_id, eligibility_status,
                        recommended_action, refund_amount, policy_explanation,
                        validation_status, validation_details,
                        correction_attempted, correction_details,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        recommendation["recommendation_id"], request_id,
                        recommendation["order_id"], recommendation["eligibility_status"],
                        recommendation["recommended_action"], recommendation["refund_amount"],
                        recommendation["policy_explanation"], recommendation["validation_status"],
                        recommendation["validation_details"],
                        recommendation["correction_attempted"],
                        recommendation["correction_details"],
                        recommendation["created_at"], recommendation["created_at"],
                    ),
                )
            cur = conn.execute(
                "UPDATE return_requests SET status = ?, error_message = ? WHERE request_id = ?",
                (request_status, error_message, request_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"Request {request_id} not found while saving results.")
    finally:
        conn.close()


def mark_request_failed(request_id: str, message: str) -> None:
    """Record that processing failed (used when the main save could not complete)."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE return_requests SET status = 'failed', error_message = ? WHERE request_id = ?",
                (message[:500], request_id),
            )
    finally:
        conn.close()


def get_request_by_token(client_token: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM return_requests WHERE client_token = ?", (client_token,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ============================================================
# Recommendations
# ============================================================

def create_recommendation(
    recommendation_id: str,
    request_id: str,
    order_id: str,
    eligibility_status: str,
    recommended_action: str,
    refund_amount: Optional[float],
    policy_explanation: str,
    created_at: str,
) -> None:
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """INSERT INTO recommendations
                   (recommendation_id, request_id, order_id, eligibility_status,
                    recommended_action, refund_amount, policy_explanation,
                    validation_status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    recommendation_id, request_id, order_id, eligibility_status,
                    recommended_action, refund_amount, policy_explanation,
                    created_at, created_at,
                ),
            )
    finally:
        conn.close()


def update_recommendation_validation(
    request_id: str,
    validation_status: str,
    validation_details: str,
    correction_attempted: int,
    correction_details: Optional[str],
    updated_at: str,
    # If validation corrected the action, also update these:
    new_action: Optional[str] = None,
    new_refund_amount: Optional[float] = None,
    new_eligibility_status: Optional[str] = None,
) -> None:
    conn = get_connection()
    try:
        with conn:
            if new_action:
                conn.execute(
                    """UPDATE recommendations
                       SET validation_status = ?, validation_details = ?,
                           correction_attempted = ?, correction_details = ?,
                           recommended_action = ?, refund_amount = ?,
                           eligibility_status = ?,
                           updated_at = ?
                       WHERE request_id = ?""",
                    (
                        validation_status, validation_details,
                        correction_attempted, correction_details,
                        new_action, new_refund_amount, new_eligibility_status,
                        updated_at, request_id,
                    ),
                )
            else:
                conn.execute(
                    """UPDATE recommendations
                       SET validation_status = ?, validation_details = ?,
                           correction_attempted = ?, correction_details = ?,
                           updated_at = ?
                       WHERE request_id = ?""",
                    (
                        validation_status, validation_details,
                        correction_attempted, correction_details,
                        updated_at, request_id,
                    ),
                )
    finally:
        conn.close()


def get_recommendation(request_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM recommendations WHERE request_id = ?", (request_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_recommendations() -> list[dict]:
    conn = get_connection()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM recommendations ORDER BY created_at DESC"
            ).fetchall()
        ]
    finally:
        conn.close()


# ============================================================
# Dashboard metrics and history queries
# ============================================================

def get_dashboard_metrics(include_tests: bool = True) -> dict:
    """
    Every number is a COUNT over persisted rows.
    Definitions (also shown in the UI):
      total               all submitted requests
      eligible            validated recommendations whose eligibility is 'eligible'
      refund / replacement / reject   validated recommendations by action
      manual_review       requests that ended in manual review
      processing_failed   requests that stopped early or could not be saved
      validation_failures requests where the Critic rejected the first recommendation
      correction_attempts requests where one correction was attempted
    """
    where = "" if include_tests else " AND rr.is_test = 0"
    conn = get_connection()
    try:
        def one(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]

        rec_base = (
            "FROM recommendations rc JOIN return_requests rr "
            "ON rr.request_id = rc.request_id WHERE 1=1" + where
        )
        passed = " AND rc.validation_status = 'passed'"
        return {
            "total": one("SELECT COUNT(*) FROM return_requests rr WHERE 1=1" + where),
            "eligible": one(f"SELECT COUNT(*) {rec_base}{passed} AND rc.eligibility_status = 'eligible'"),
            "refund_recommended": one(f"SELECT COUNT(*) {rec_base}{passed} AND rc.recommended_action = 'refund'"),
            "replacement_recommended": one(f"SELECT COUNT(*) {rec_base}{passed} AND rc.recommended_action = 'replacement'"),
            "rejected": one(f"SELECT COUNT(*) {rec_base}{passed} AND rc.recommended_action = 'reject'"),
            "manual_review": one(
                "SELECT COUNT(*) FROM return_requests rr "
                "WHERE rr.status = 'manual_review'" + where),
            "processing_failed": one(
                "SELECT COUNT(*) FROM return_requests rr WHERE rr.status = 'failed'" + where),
            "validation_failures": one(
                "SELECT COUNT(DISTINCT al.request_id) FROM agent_logs al "
                "JOIN return_requests rr ON rr.request_id = al.request_id "
                "WHERE al.step_type = 'validation' AND al.verdict = 'failed'" + where),
            "correction_attempts": one(f"SELECT COUNT(*) {rec_base} AND rc.correction_attempted = 1"),
        }
    finally:
        conn.close()


def search_requests(
    query: str = "",
    status: str = "",
    action: str = "",
    include_tests: bool = True,
    limit: int = 200,
) -> list[dict]:
    """
    Request list joined with its recommendation. All filters are optional and
    always passed as bound parameters (no string-built SQL from user input).
    """
    sql = """
        SELECT rr.request_id, rr.order_id, rr.reason, rr.submitted_at,
               rr.status, rr.is_test, rr.error_message,
               rc.recommended_action, rc.validation_status, rc.refund_amount,
               rc.eligibility_status, rc.correction_attempted
        FROM   return_requests rr
        LEFT JOIN recommendations rc ON rr.request_id = rc.request_id
        WHERE  1 = 1
    """
    params: list = []
    q = (query or "").strip()
    if q:
        sql += " AND (rr.request_id LIKE ? OR rr.order_id LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if status:
        sql += " AND rr.status = ?"
        params.append(status)
    if action:
        sql += " AND rc.recommended_action = ?"
        params.append(action)
    if not include_tests:
        sql += " AND rr.is_test = 0"
    sql += " ORDER BY rr.submitted_at DESC, rr.request_id LIMIT ?"
    params.append(int(limit))
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_recent_requests(limit: int = 10) -> list[dict]:
    return search_requests(limit=limit)


def count_requests() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM return_requests").fetchone()[0]
    finally:
        conn.close()


def search_requests_page(
    query: str = "",
    status: str = "",
    action: str = "",
    include_tests: bool = True,
    limit: int = 15,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """One page of search_requests() plus the total number of matches (for pagination)."""
    total = len(search_requests(query, status, action, include_tests, limit=100000))
    rows = search_requests(query, status, action, include_tests, limit=limit + offset)[offset:]
    return rows, total


def count_by_status(include_tests: bool = True) -> dict:
    """Number of requests per request status (pending / validated / manual_review / failed ...)."""
    sql = "SELECT status, COUNT(*) AS n FROM return_requests"
    if not include_tests:
        sql += " WHERE is_test = 0"
    sql += " GROUP BY status"
    conn = get_connection()
    try:
        return {r["status"]: r["n"] for r in conn.execute(sql).fetchall()}
    finally:
        conn.close()


def get_attention_requests(kind: str, include_tests: bool = True, limit: int = 5) -> list[dict]:
    """
    Newest requests that need a human's eye:
      'validation_failure'  the Critic rejected the first recommendation
      'manual_review'       the request ended in manual review
    """
    if kind == "validation_failure":
        where = ("rr.request_id IN (SELECT request_id FROM agent_logs "
                 "WHERE step_type = 'validation' AND verdict = 'failed')")
    elif kind == "manual_review":
        where = "rr.status = 'manual_review'"
    else:
        raise ValueError("unknown kind")
    if not include_tests:
        where += " AND rr.is_test = 0"
    sql = f"""
        SELECT rr.request_id, rr.order_id, rr.reason, rr.submitted_at, rr.status,
               rc.recommended_action, rc.validation_status, rc.correction_attempted
        FROM return_requests rr
        LEFT JOIN recommendations rc ON rc.request_id = rr.request_id
        WHERE {where}
        ORDER BY rr.submitted_at DESC, rr.request_id LIMIT ?
    """
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, (int(limit),)).fetchall()]
    finally:
        conn.close()
