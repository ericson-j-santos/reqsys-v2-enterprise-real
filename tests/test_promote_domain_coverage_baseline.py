from scripts.promote_domain_coverage_baseline import promote


def test_promotes_first_measured_baseline() -> None:
    policy = {"baseline": {}}
    report = {"domains": {"core": {"coverage_percent": 96.01, "statements": 1253, "eligible_for_baseline": True}}}

    updated, entry = promote(policy, report, measured_at="2026-07-10T01:00:00Z", source_sha="abc")

    assert updated["baseline"] == {"core": 96.01}
    assert updated["mode"] == "regression_blocking"
    assert entry["changes"]["core"] == {"from": None, "to": 96.01}


def test_never_lowers_existing_baseline() -> None:
    policy = {"baseline": {"core": 96.01}}
    report = {"domains": {"core": {"coverage_percent": 95.0, "statements": 1253, "eligible_for_baseline": True}}}

    updated, entry = promote(policy, report, measured_at="2026-07-10T01:00:00Z", source_sha="abc")

    assert updated["baseline"]["core"] == 96.01
    assert entry["changes"] == {}


def test_ignores_domains_without_statements() -> None:
    policy = {"baseline": {}}
    report = {"domains": {"runtime": {"coverage_percent": 0.0, "statements": 0, "eligible_for_baseline": False}}}

    updated, entry = promote(policy, report, measured_at="2026-07-10T01:00:00Z", source_sha="abc")

    assert updated["baseline"] == {}
    assert entry["measured"] == {}
