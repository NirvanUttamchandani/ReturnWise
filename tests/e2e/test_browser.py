"""
Browser end-to-end tests: the real FastAPI server (temporary SQLite file) serving the built React app,
driven by Chromium through Playwright. Skipped when frontend/dist or Playwright is unavailable.

    cd frontend; npm run build; cd ..
    python -m pytest tests/e2e -v
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pytest.importorskip("playwright.sync_api")
if not os.path.isfile(os.path.join(ROOT, "frontend", "dist", "index.html")):
    pytest.skip("frontend/dist is missing - run `npm run build` in frontend/", allow_module_level=True)

from playwright.sync_api import sync_playwright  # noqa: E402

import config  # noqa: E402


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    db = str(tmp_path_factory.mktemp("e2e") / "e2e.db")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = {**os.environ, "RETURNWISE_DB_PATH": db}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--port", str(port), "--log-level", "warning"],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/health", timeout=1); break
        except Exception:
            time.sleep(0.25)
    else:
        proc.kill(); pytest.fail("API server did not start")
    yield {"base": base, "db": db}
    proc.terminate(); proc.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser, server):
    ctx = browser.new_context(viewport={"width": 1366, "height": 850})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    yield pg
    ctx.close()


def db_row(server, request_id):
    import sqlite3
    c = sqlite3.connect(server["db"]); c.row_factory = sqlite3.Row
    r = c.execute("SELECT * FROM return_requests WHERE request_id=?", (request_id,)).fetchone()
    n_logs = c.execute("SELECT COUNT(*) FROM agent_logs WHERE request_id=?", (request_id,)).fetchone()[0]
    c.close()
    return r, n_logs


def submit(page, server, order, reason):
    page.goto(server["base"] + "/new")
    page.fill("#order_id", order); page.select_option("#reason", reason)
    page.get_by_role("button", name="Submit return").click()
    page.wait_for_selector("[data-testid=request-id]")
    return page.inner_text("[data-testid=request-id]")


def test_empty_overview_then_submit_and_persist(page, server):
    page.goto(server["base"])
    page.get_by_role("heading", name="Overview").wait_for()
    page.get_by_text("No return requests yet").wait_for()                       # empty state on a fresh database
    rid = submit(page, server, "ORD-001", "defective")
    row, n_logs = db_row(server, rid)
    assert row["order_id"] == "ORD-001" and row["status"] == "validated"          # id shown == id stored
    assert n_logs == 5
    assert "No refund has been paid" in page.inner_text("main")
    assert "refunded" not in page.inner_text("main").lower()
    assert page.errors == []


def test_history_and_detail_survive_a_reload(page, server):
    rid = submit(page, server, "ORD-002", "changed_mind")
    page.goto(server["base"] + f"/requests/{rid}")
    page.get_by_role("heading", name="Agent timeline").wait_for()
    assert "Rejection Recommended" in page.inner_text("main")
    page.reload()
    page.get_by_role("heading", name="Agent timeline").wait_for()
    assert rid in page.inner_text("main") and "ORD-002" in page.inner_text("main")
    page.goto(server["base"] + "/requests?q=ORD-002")
    page.get_by_role("link", name=rid).wait_for()
    page.reload()
    assert page.get_by_label("Search requests").input_value() == "ORD-002"       # filter restored from the URL
    page.get_by_role("link", name=rid).wait_for()
    assert page.errors == []


def test_unknown_order_shows_error_and_skipped_stages(page, server):
    rid = submit(page, server, "FAKE-999", "defective")
    page.goto(server["base"] + f"/workflow/{rid}")
    page.get_by_role("list", name="Agent pipeline").wait_for()
    text = page.inner_text("main")
    assert "Error" in text and text.count("Skipped") == 3 and "Processing Failed" in text
    assert db_row(server, rid)[0]["status"] == "failed"
    assert page.errors == []


def test_testing_lab_runs_real_workflow_and_shows_correction_loop(page, server):
    page.goto(server["base"] + "/lab")
    page.get_by_role("button", name="Run scenario SC-09").click()
    page.get_by_text("All checks passed").wait_for()
    rid = page.locator("[data-testid=scenario-SC-09]").get_by_text("Saved as test request").inner_text().split()[-1]
    row, n_logs = db_row(server, rid)
    assert row["is_test"] == 1 and n_logs == 7                                   # real stored workflow, 5 agents + correction + revalidation
    page.locator("[data-testid=scenario-SC-09]").get_by_role("link", name="Open workflow").click()
    page.get_by_label("Correction loop").wait_for()
    assert "Critic rejected" in page.inner_text("main")
    page.get_by_role("button", name=" Validation (revalidation)".strip()).click()
    assert "Passed" in page.get_by_role("region", name="Stage details").inner_text() or "PASSED" in page.get_by_role("region", name="Stage details").inner_text()
    assert page.errors == []


def test_run_all_scenarios_pass(page, server):
    page.goto(server["base"] + "/lab")
    page.get_by_role("button", name="Run all scenarios").click()
    page.get_by_test_id("lab-summary").wait_for(timeout=30000)
    assert "12 of 12 scenarios passed" in page.get_by_test_id("lab-summary").inner_text()


def test_overview_numbers_match_the_database(page, server):
    import sqlite3
    c = sqlite3.connect(server["db"])
    total = c.execute("SELECT COUNT(*) FROM return_requests WHERE is_test=0").fetchone()[0]; c.close()
    page.goto(server["base"])
    page.get_by_test_id("kpi-Total requests").wait_for()
    assert page.get_by_test_id("kpi-Total requests").inner_text().strip() == str(total)


def test_mobile_navigation_and_no_horizontal_scroll(browser, server):
    ctx = browser.new_context(viewport={"width": 390, "height": 800}); pg = ctx.new_page()
    errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(server["base"]); pg.get_by_role("heading", name="Overview").wait_for()
    assert not pg.get_by_test_id("sidebar").is_visible()
    pg.get_by_label("Open navigation").click()
    assert pg.get_by_test_id("drawer").is_visible()
    pg.get_by_test_id("drawer").get_by_role("link", name="New Return").click()
    pg.get_by_role("heading", name="New Return").wait_for()
    assert not pg.get_by_test_id("drawer").is_visible()
    for path in ("/", "/new", "/requests", "/lab", "/workflow", "/resolution"):
        pg.goto(server["base"] + path); pg.wait_for_load_state("networkidle")
        assert not pg.evaluate("document.documentElement.scrollWidth > innerWidth"), path
    assert errors == []
    ctx.close()


def test_backend_validation_blocks_bad_input_from_the_browser(page, server):
    page.goto(server["base"] + "/new")
    page.fill("#order_id", "ORD 1; DROP TABLE orders"); page.select_option("#reason", "defective")
    page.get_by_role("button", name="Submit return").click()
    page.get_by_text("Order ID may contain only letters").wait_for()
    assert "request-id" not in page.content()
