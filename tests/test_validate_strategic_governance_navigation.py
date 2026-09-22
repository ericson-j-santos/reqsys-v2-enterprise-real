from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_strategic_governance_navigation import build_report


def test_strategic_governance_navigation_validator_passes_for_static_assets() -> None:
    report = build_report(
        REPO_ROOT,
        REPO_ROOT / "docs/ops-dashboard/strategic-governance-navigation.json",
    )

    assert report["status"] == "passed"
    assert report["mode"] == "offline_static_validation"
    assert "strategic_governance_page" in report["manifest"]["validated_links"]
    assert "./strategic-governance.html" in report["entrypoint"]["validated_fragments"]
    assert "no_network_calls" in report["guardrails"]


def test_strategic_governance_page_exposes_executive_trend_artifact() -> None:
    html = (REPO_ROOT / "docs/ops-dashboard/strategic-governance.html").read_text(encoding="utf-8")

    assert "Executive Trend History" in html
    assert "./data/executive-trend-history.json" in html
    assert "executive-trend-history.json" in html
    assert "recommendation-only" in html
    assert "não substitui CI" in html


def main() -> int:
    test_strategic_governance_navigation_validator_passes_for_static_assets()
    test_strategic_governance_page_exposes_executive_trend_artifact()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
