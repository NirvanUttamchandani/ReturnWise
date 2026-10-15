"""
ReturnWise Database Module
Connection management, schema creation and backward-compatible migration.
"""

import sqlite3
import os
import logging

import config

logger = logging.getLogger(__name__)

# Columns added after the first release. Older database files are upgraded in
# place with ALTER TABLE ... ADD COLUMN, so existing records are never lost.
_MIGRATIONS = {
    "return_requests": [
        ("client_token", "TEXT"),
        ("error_message", "TEXT"),
    ],
    "agent_logs": [
        ("step_type", "TEXT NOT NULL DEFAULT 'agent'"),
        ("verdict", "TEXT"),
        ("input_json", "TEXT"),
        ("output_json", "TEXT"),
    ],
}

# Created after the migration because they reference migrated columns.
_INDEXES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_requests_client_token "
    "ON return_requests(client_token) WHERE client_token IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_logs_request_order "
    "ON agent_logs(request_id, execution_order)",
]


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory and foreign-key enforcement."""
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    """Create tables, migrate older files, create indexes and seed data (idempotent)."""
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema_sql = fh.read()

    conn = get_connection()
    try:
        with conn:
            conn.executescript(schema_sql)
        _migrate(conn)
        for stmt in _INDEXES:
            try:
                with conn:
                    conn.execute(stmt)
            except sqlite3.DatabaseError as exc:
                logger.warning("Index not created (legacy data?): %s", exc)
        logger.info("Schema applied successfully.")
    finally:
        conn.close()

    # Seed only into empty tables (never overwrites existing rows)
    from database.seed_data import seed_all
    seed_all()
    logger.info("Database initialised.")


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in _MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in columns:
            if name not in existing:
                with conn:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                logger.info("Migrated: %s.%s added.", table, name)
