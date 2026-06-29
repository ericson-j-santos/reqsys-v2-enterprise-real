#!/usr/bin/env python3
"""Report-only validator for Camada de Testes — Padrão Ouro (Tier 1)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "audit" / "camada-testes"
AAC = ROOT / "docs" / "architecture" / "camada-testes" / "architecture-as-code.json"
LIVING_INDEX = ROOT / "docs" / "padrao-ouro" / "living-architecture-index.json"

GOVERNANCE_FILES = [
    "docs/padrao-ouro/TESTING_PLAYBOOK.md",
    "docs/runbooks/camada-testes-padrao-ouro.md",
    "docs/contracts/camada-testes-padrao-ouro.schema.json",
    "docs/architecture/camada-testes/architecture-as-code.json",
    ".github/workflows/camada-testes-padrao-ouro.yml",
    "tests/test_camada_testes_padrao_ouro.py",
]

TEST_LAYERS: list[dict[str, Any]] = [
    {"id": "backend_pytest", "path": "backend/tests", "runner": "pytest", "ci_gate": True},
    {"id": "frontend_vitest", "path": "frontend/src", "runner": "vitest", "ci_gate": False},
    {"id": "frontend_playwright", "path": "frontend/tests/e2e", "runner": "playwright", "ci_gate": True},
    {"id": "governance_pytest", "path": "tests", "runner": "pytest", "ci_gate": False},
    {"id": "alt_frontends_e2e", "path": "e2e", "runner": "playwright", "ci_gate": False},
]

REQUIRED_ANCHOR_FILES = [
    "backend/tests/conftest.py",
    "frontend/src/test/setup.js",
    "frontend/tests/e2e/responsividade.spec.js",
    "frontend/playwright.config.js",
    "backend/pyproject.toml",
    ".github/workflows/ci.yml",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    layer_results: list[dict[str, Any]] = []
    governance_ok = 0

    for rel in GOVERNANCE_FILES:
        if (ROOT / rel).exists():
            governance_ok += 1
        else:
            issues.append({"severity": "error", "type": "missing_governance", "target": rel})

    for layer in TEST_LAYERS:
        rel = layer["path"]
        exists = (ROOT / rel).exists()
        layer_results.append({**layer, "exists": exists})
        if not exists:
            issues.append({"severity": "error", "type": "missing_layer", "target": rel})

    for rel in REQUIRED_ANCHOR_FILES:
        if not (ROOT / rel).exists():
            issues.append({"severity": "error", "type": "missing_anchor", "target": rel})

    if LIVING_INDEX.exists():
        index = json.loads(LIVING_INDEX.read_text(encoding="utf-8"))
        tier1 = index.get("tier1_docs", {})
        if tier1.get("testing_playbook") != "docs/padrao-ouro/TESTING_PLAYBOOK.md":
            issues.append({
                "severity": "error",
                "type": "tier1_not_indexed",
                "target": "living-architecture-index.json tier1_docs.testing_playbook",
            })
        modules = index.get("modules", {})
        if "tests" not in modules:
            issues.append({
                "severity": "warning",
                "type": "tests_module_missing",
                "target": "living-architecture-index.json modules.tests",
            })
    else:
        issues.append({"severity": "error", "type": "missing_living_index", "target": str(LIVING_INDEX)})

    if AAC.exists():
        aac = json.loads(AAC.read_text(encoding="utf-8"))
        for layer_id in ("backend_pytest", "frontend_vitest", "frontend_playwright", "governance_pytest", "alt_frontends_e2e"):
            if layer_id not in aac.get("layers", {}):
                issues.append({"severity": "error", "type": "missing_aac_layer", "target": layer_id})
    else:
        issues.append({"severity": "error", "type": "missing_aac", "target": str(AAC)})

    ci_yml = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8") if (ROOT / ".github/workflows/ci.yml").exists() else ""
    for marker in ("pytest", "responsividade.spec.js", "cov-fail-under"):
        if marker not in ci_yml:
            issues.append({"severity": "warning", "type": "ci_marker_missing", "target": marker})

    layers_ok = sum(1 for layer in layer_results if layer["exists"])
    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    summary = {
        "governance_ok": governance_ok,
        "governance_total": len(GOVERNANCE_FILES),
        "layers_ok": layers_ok,
        "layers_total": len(TEST_LAYERS),
        "errors": errors,
        "warnings": warnings,
    }
    return issues, summary, layer_results


def build_report(
    issues: list[dict[str, Any]],
    summary: dict[str, Any],
    layer_results: list[dict[str, Any]],
) -> dict[str, Any]:
    status = "failed" if summary["errors"] else ("passed_with_warnings" if summary["warnings"] else "passed")
    return {
        "schema_version": "1.0.0",
        "generated_at": now_iso(),
        "layer_id": "camada-testes",
        "layer_name": "Camada de Testes — Padrão Ouro",
        "mode": "report_only",
        "status": status,
        "summary": summary,
        "layers": layer_results,
        "issues": issues,
        "artifacts": {
            "report": "audit/camada-testes/camada-testes-padrao-ouro-report.json",
            "architecture_as_code": "docs/architecture/camada-testes/architecture-as-code.json",
        },
    }


def main() -> int:
    issues, summary, layer_results = validate()
    report = build_report(issues, summary, layer_results)
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "camada-testes-padrao-ouro-report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "summary": summary}, indent=2))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
