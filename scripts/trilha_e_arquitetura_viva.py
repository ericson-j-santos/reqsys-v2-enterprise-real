#!/usr/bin/env python3
"""Report-only validator and report generator for Trilha E — Arquitetura Viva."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRILHA = ROOT / "docs" / "architecture" / "trilha-e"
OUT = ROOT / "audit" / "trilha-e"

REQUIRED_FILES = [
    "architecture-as-code.json",
    "inventory.json",
    "runtime-topology.json",
    "diagrams.json",
    "fluxo-navegavel.json",
    "index.html",
]

REQUIRED_CAPABILITIES = [
    "diagramas_vivos",
    "adrs",
    "runtime_topology",
    "fluxo_navegavel",
    "inventory",
    "architecture_as_code",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_repo_path(value: str) -> bool:
    return (
        bool(value)
        and not value.startswith(("http://", "https://", "/api"))
        and ("/" in value or value.endswith((".md", ".json", ".html", ".yml", ".yaml", ".py")))
    )


def collect_internal_paths(aac: dict[str, Any], inventory: dict[str, Any], fluxo: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    gov = aac.get("governance", {})
    paths.update(filter(None, [gov.get("adr"), gov.get("runbook"), gov.get("workflow")]))

    for cap in aac.get("capabilities", {}).values():
        if isinstance(cap, dict):
            for value in cap.values():
                if isinstance(value, str) and is_repo_path(value):
                    paths.add(value)

    for section in ("services", "api_modules", "workflows", "dashboards"):
        for item in inventory.get(section, []):
            path = item.get("path")
            if path and not path.endswith("/"):
                paths.add(path)

    for adr in inventory.get("adrs", []):
        paths.add(adr.get("path", ""))

    for node in fluxo.get("nodes", []):
        href = node.get("href", "")
        if href and not href.startswith(("http", "/api", "#")):
            paths.add(href.split("#")[0])

    paths.discard("")
    return paths


def validate(aac: dict[str, Any], inventory: dict[str, Any], diagrams: dict[str, Any], fluxo: dict[str, Any], topology: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    for capability in REQUIRED_CAPABILITIES:
        if capability not in aac.get("capabilities", {}):
            issues.append({"severity": "error", "type": "missing_capability", "target": capability})

    gold = aac.get("gold_standard", {})
    if gold.get("tier") != "padrao_ouro" or gold.get("status") != "canonical":
        issues.append({"severity": "error", "type": "gold_standard_not_canonical", "target": gold})

    for filename in REQUIRED_FILES:
        if not (TRILHA / filename).exists():
            issues.append({"severity": "error", "type": "missing_trilha_file", "target": filename})

    for diagram in diagrams.get("diagrams", []):
        if not diagram.get("mermaid"):
            issues.append({"severity": "warning", "type": "diagram_without_mermaid", "target": diagram.get("id", "unknown")})

    node_ids = {node["id"] for node in fluxo.get("nodes", [])}
    for edge in fluxo.get("edges", []):
        if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
            issues.append({"severity": "warning", "type": "fluxo_edge_unknown_node", "target": f"{edge.get('from')}->{edge.get('to')}"})

    for adr in inventory.get("adrs", []):
        adr_path = adr.get("path", "")
        if adr_path and not (ROOT / adr_path).exists():
            issues.append({"severity": "warning", "type": "adr_path_missing", "target": adr_path})

    expected_nodes = {"reqsys-api", "ops-dashboard", "runtime-evidence-store", "incident-timeline"}
    actual_nodes = {node["id"] for node in topology.get("runtime_nodes", [])}
    if not expected_nodes.issubset(actual_nodes):
        issues.append({"severity": "warning", "type": "topology_runtime_misalignment", "target": sorted(expected_nodes - actual_nodes)})

    for candidate in sorted(collect_internal_paths(aac, inventory, fluxo)):
        if not (ROOT / candidate).exists():
            issues.append({"severity": "warning", "type": "missing_internal_path", "target": candidate})

    return issues


def build_report(issues: list[dict[str, Any]], aac: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    errors = sum(1 for item in issues if item["severity"] == "error")
    warnings = sum(1 for item in issues if item["severity"] == "warning")
    status = "failed" if errors else ("passed_with_warnings" if warnings else "passed")
    return {
        "schema_version": "1.0.0",
        "generated_at": now_iso(),
        "trail_id": "trilha-e",
        "trail_name": "Arquitetura Viva",
        "mode": "report_only",
        "status": status,
        "summary": {
            "capabilities": len(REQUIRED_CAPABILITIES),
            "adrs_indexed": len(inventory.get("adrs", [])),
            "services": len(inventory.get("services", [])),
            "workflows": len(inventory.get("workflows", [])),
            "errors": errors,
            "warnings": warnings,
            "gold_standard": aac.get("gold_standard", {}).get("tier"),
        },
        "capabilities": list(aac.get("capabilities", {}).keys()),
        "issues": issues,
        "artifacts": {
            "architecture_as_code": "docs/architecture/trilha-e/architecture-as-code.json",
            "hub": "docs/architecture/trilha-e/index.html",
            "adr": "docs/adr/ADR-035-trilha-e-arquitetura-viva.md",
        },
    }


def main() -> int:
    aac = load_json(TRILHA / "architecture-as-code.json")
    inventory = load_json(TRILHA / "inventory.json")
    diagrams = load_json(TRILHA / "diagrams.json")
    fluxo = load_json(TRILHA / "fluxo-navegavel.json")
    topology = load_json(TRILHA / "runtime-topology.json")

    issues = validate(aac, inventory, diagrams, fluxo, topology)
    report = build_report(issues, aac, inventory)

    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "trilha-e-arquitetura-viva-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
