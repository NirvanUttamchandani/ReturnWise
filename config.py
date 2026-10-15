"""
ReturnWise Configuration Module
Centralizes all application-wide settings and constants.
"""

import os

# ---------------------------------------------------------------------------
# Application Identity
# ---------------------------------------------------------------------------
APP_NAME = "ReturnWise"
APP_VERSION = "1.1.0"
APP_DESCRIPTION = "Multi-Agent AI System for Intelligent E-commerce Return and Refund Resolution"

# ---------------------------------------------------------------------------
# Reference Date
# NOTE: In production this would be datetime.date.today(). For this PoC we
# pin the reference date so that return-window calculations are deterministic
# and reproducible, regardless of when the application is run.
# ---------------------------------------------------------------------------
REFERENCE_DATE_STR = "2025-02-15"   # Pinned reference date (YYYY-MM-DD)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# RETURNWISE_DB_PATH lets tests / deployments point at another file.
DB_PATH = os.getenv("RETURNWISE_DB_PATH") or os.path.join(BASE_DIR, "database", "returnwise.db")

# ---------------------------------------------------------------------------
# No LLM is used. Every decision is made by deterministic Python rules, so the
# app needs no API key, no internet and no paid service.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Business-rule guardrails (category windows and restrictions live in the
# return_policies table, seeded from the fictional policy in policies/).
# ---------------------------------------------------------------------------

# Free-text limits (input validation)
MAX_DESCRIPTION_LENGTH = 500
ORDER_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$"

# Maximum refund cap for a single request (safety guardrail – not a policy limit)
MAX_REFUND_CAP = 50000.00

# ---------------------------------------------------------------------------
# Workflow Safety
# ---------------------------------------------------------------------------
MAX_CORRECTION_ATTEMPTS = 1   # Critic Agent may request at most one correction

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("RETURNWISE_LOG_LEVEL", "INFO")
