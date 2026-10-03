"""Tests for Trilha E — Arquitetura Viva (architecture-as-code)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRILHA = ROOT / "docs" / "architecture" / "trilha-e"
SCRIPT = ROOT / "scripts" / "trilha_e_arquitetura_viva.py"


def _load(name: str) -> dict:
    return json.loads((TRILHA / name).read_text(encoding="utf-8"))


def test_trilha_e_required_files_exist():
    required = [
        "architecture-as-code.json",
        "inventory.json",
        "runtime-topology.json",
        "diagrams.json",
        "fluxo-navegavel.json",
        "index.html",
    ]
    for filename in required:
        assert (TRILHA / filename).exists(), filename


def test_architecture_as_code_has_six_capabilities():
    aac = _load("architecture-as-code.json")
    assert aac["trail_id"] == "trilha-e"
    capabilities = aac["capabilities"]
    assert set(capabilities) == {
        "diagramas_vivos",
        "adrs",
        "runtime_topology",
        "fluxo_navegavel",
        "inventory",
        "architecture_as_code",
    }
    for cap in capabilities.values():
        assert cap["status"] == "active"


def test_diagrams_have_mermaid_content():
    diagrams = _load("diagrams.json")
    assert len(diagrams["diagrams"]) >= 4
    for diagram in diagrams["diagrams"]:
        assert diagram.get("mermaid"), diagram["id"]


def test_fluxo_navegavel_graph_is_consistent():
    fluxo = _load("fluxo-navegavel.json")
    node_ids = {node["id"] for node in fluxo["nodes"]}
    for edge in fluxo["edges"]:
        assert edge["from"] in node_ids
        assert edge["to"] in node_ids


def test_inventory_adr_paths_exist():
    inventory = _load("inventory.json")
    assert len(inventory["adrs"]) >= 20
    for adr in inventory["adrs"]:
        path = ROOT / adr["path"]
        assert path.exists(), adr["path"]


def test_runtime_topology_aligns_with_backend_contract():
    topology = _load("runtime-topology.json")
    node_ids = {node["id"] for node in topology["runtime_nodes"]}
    assert "reqsys-api" in node_ids
    assert topology["coverage"]["workflow_dependencies"] >= 4


def test_generator_produces_passing_report():
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["trail_id"] == "trilha-e"
    assert report["status"] in {"passed", "passed_with_warnings"}
    assert report["summary"]["errors"] == 0
    report_path = ROOT / "audit" / "trilha-e" / "trilha-e-arquitetura-viva-report.json"
    assert report_path.exists()
