from __future__ import annotations

import json
from pathlib import Path


def test_strategic_governance_navigation_manifest_links_core_surfaces() -> None:
    manifest = json.loads(Path("docs/ops-dashboard/strategic-governance-navigation.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "1.0.0"
    assert manifest["links"]["strategic_governance_page"] == "docs/ops-dashboard/strategic-governance.html"
    assert manifest["links"]["strategic_governance_data"] == "docs/ops-dashboard/data/strategic-governance-index.json"
    assert manifest["links"]["ops_dashboard"] == "docs/ops-dashboard/index.html"
    assert manifest["links"]["operational_evidence_hub"] == "docs/dashboard/operational-evidence-hub.html"
    assert "no_runtime_github_api_call" in manifest["guardrails"]


def test_strategic_governance_navigation_entrypoint_is_static_and_navigable() -> None:
    html = Path("docs/ops-dashboard/strategic-governance-navigation.html").read_text(encoding="utf-8")

    assert "Strategic Governance Navigation" in html
    assert "./strategic-governance.html" in html
    assert "./data/strategic-governance-index.json" in html
    assert "./index.html" in html
    assert "../dashboard/operational-evidence-hub.html" in html
