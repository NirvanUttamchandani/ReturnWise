"""Shared fixtures: every test that asks for `db` gets a brand-new, seeded SQLite file."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    from database.db import init_db
    init_db()
    return config.DB_PATH


@pytest.fixture
def process(db):
    """Helper: submit + run the workflow through the service layer (is_test=True)."""
    import services.request_service as svc

    def _go(order_id, reason, description="Test", **kw):
        return svc.process_return(order_id, reason, description, is_test=True, **kw)

    return _go
