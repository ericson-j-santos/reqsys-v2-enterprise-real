#!/usr/bin/env python3
"""Validate Strategic Governance static navigation contracts.

This validator is deterministic and offline. It verifies that the Strategic
Governance pages, JSON artifacts and navigation manifest keep pointing to local
static assets that exist in the repository. It is designed for CI/report-only
use and does not call external APIs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_exists(repo_root: Path, relative_path: str) -> None:
    full_path = repo_root / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"navigation target does not exist: {relative_path}")


def validate_manifest(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    links = manifest.get("links") or {}
    required_links = [
        "strategic_governance_page",
        "strategic_governance_data",
        "runtime_executive_index",
        "ops_dashboard",
        "operational_evidence_hub",
    ]

    missing_keys = [key for key in required_links if not links.get(key)]
    if missing_keys:
        raise ValueError(f"missing required navigation links: {missing_keys}")

    for key in required_links:
        assert_exists(repo_root, str(links[key]))

    recommended_surfaces = manifest.get("recommended_surfaces") or []
    if len(recommended_surfaces) < 2:
        raise ValueError("expected at least two recommended surfaces")

    for surface in recommended_surfaces:
        assert_exists(repo_root, str(surface["surface"]))
        if not surface.get("href") or not surface.get("label"):
            raise ValueError(f"invalid recommended surface entry: {surface}")

    guardrails = set(manifest.get("guardrails") or [])
    required_guardrails = {
        "static_navigation_only",
        "no_runtime_github_api_call",
        "does_not_change_ci_gates",
        "does_not_replace_evidence_gate",
    }
    missing_guardrails = sorted(required_guardrails - guardrails)
    if missing_guardrails:
        raise ValueError(f"missing required guardrails: {missing_guardrails}")

    return {
        "schema_version": manifest.get("schema_version"),
        "validated_links": required_links,
        "recommended_surface_count": len(recommended_surfaces),
        "guardrail_count": len(guardrails),
    }


def validate_navigation_entrypoint(repo_root: Path) -> dict[str, Any]:
    html_path = repo_root / "docs/ops-dashboard/strategic-governance-navigation.html"
    if not html_path.exists():
        raise FileNotFoundError(f"navigation entrypoint not found: {html_path}")
    html = html_path.read_text(encoding="utf-8")
    required_fragments = [
        "./strategic-governance.html",
        "./data/strategic-governance-index.json",
        "./index.html",
        "../dashboard/operational-evidence-hub.html",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in html]
    if missing:
        raise ValueError(f"navigation entrypoint missing fragments: {missing}")
    return {"validated_fragments": required_fragments}


def build_report(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "status": "passed",
        "mode": "offline_static_validation",
        "manifest": validate_manifest(repo_root, manifest_path),
        "entrypoint": validate_navigation_entrypoint(repo_root),
        "guardrails": [
            "offline_only",
            "no_network_calls",
            "no_runtime_mutation",
            "report_only_validation",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Strategic Governance navigation")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--manifest",
        default="docs/ops-dashboard/strategic-governance-navigation.json",
    )
    parser.add_argument(
        "--output",
        default="artifacts/strategic-governance-navigation-validation.json",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    manifest_path = repo_root / args.manifest
    report = build_report(repo_root, manifest_path)
    output_path = repo_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
