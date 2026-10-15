"""
ReturnWise Reporting Service
Read-only queries for the dashboard, history and sample-order list.
Every number is computed from persisted rows; nothing is hardcoded.
"""

import database.repository as repo


def get_dashboard_metrics(include_tests: bool = True) -> dict:
    return repo.get_dashboard_metrics(include_tests=include_tests)


def get_recent_requests(limit: int = 10, include_tests: bool = True) -> list[dict]:
    return repo.search_requests(include_tests=include_tests, limit=limit)


def search_requests(query: str = "", status: str = "", action: str = "",
                    include_tests: bool = True, limit: int = 200) -> list[dict]:
    return repo.search_requests(query, status, action, include_tests, limit)


def get_all_orders() -> list[dict]:
    return repo.get_all_orders()


def get_all_policies() -> list[dict]:
    return repo.get_all_policies()


def search_requests_page(query: str = "", status: str = "", action: str = "",
                         include_tests: bool = True, limit: int = 15, offset: int = 0):
    return repo.search_requests_page(query, status, action, include_tests, limit, offset)


def get_status_breakdown(include_tests: bool = True) -> dict:
    return repo.count_by_status(include_tests)


def get_attention(kind: str, include_tests: bool = True, limit: int = 5) -> list[dict]:
    return repo.get_attention_requests(kind, include_tests, limit)
