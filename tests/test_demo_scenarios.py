"""Every demo scenario must pass against data READ BACK from the database."""

import pytest

import services.demo_service as demo


@pytest.mark.parametrize("scenario", demo.get_scenarios(), ids=lambda s: s["id"])
def test_scenario_passes(db, scenario):
    result = demo.run_scenario(scenario)
    failed = [c for c in result["checks"] if not c["passed"]]
    assert result["passed"], failed


def test_a_wrong_expectation_is_reported_as_failed(db):
    """Guard against 'always pass': change an expectation and the scenario must fail."""
    sc = dict(demo.get_scenarios()[0])
    sc["expect"] = dict(sc["expect"], action="reject")
    result = demo.run_scenario(sc)
    assert not result["passed"]
    assert any(c["check"] == "recommended action" and not c["passed"] for c in result["checks"])


def test_missing_field_scenario_writes_nothing(db):
    import database.repository as repo
    sc = next(s for s in demo.get_scenarios() if s["id"] == "SC-06")
    assert demo.run_scenario(sc)["passed"] and repo.count_requests() == 0
