from __future__ import annotations

from pathlib import Path

from scripts.validate_strategic_governance_navigation import build_report


def test_strategic_governance_navigation_validator_passes_for_static_assets() -> None:
    report = build_report(
        Path("."),
        Path("docs/ops-dashboard/strategic-governance-navigation.json"),
    )

    assert report["status"] == "passed"
    assert report["mode"] == "offline_static_validation"
    assert "strategic_governance_page" in report["manifest"]["validated_links"]
    assert "./strategic-governance.html" in report["entrypoint"]["validated_fragments"]
    assert "no_network_calls" in report["guardrails"]
