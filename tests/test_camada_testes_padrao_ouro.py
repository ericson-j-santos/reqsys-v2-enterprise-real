from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "camada_testes_padrao_ouro.py"
REPORT = ROOT / "audit" / "camada-testes" / "camada-testes-padrao-ouro-report.json"
SCHEMA = ROOT / "docs" / "contracts" / "camada-testes-padrao-ouro.schema.json"
AAC = ROOT / "docs" / "architecture" / "camada-testes" / "architecture-as-code.json"
PLAYBOOK = ROOT / "docs" / "padrao-ouro" / "TESTING_PLAYBOOK.md"


def test_playbook_tier1_exists() -> None:
    assert PLAYBOOK.exists(), "TESTING_PLAYBOOK.md missing"


def test_architecture_as_code_lists_five_layers() -> None:
    aac = json.loads(AAC.read_text(encoding="utf-8"))
    assert aac["layer_id"] == "camada-testes"
    assert len(aac["layers"]) == 5
    assert "backend_pytest" in aac["layers"]
    assert "frontend_playwright" in aac["layers"]


def test_validator_generates_report_with_required_fields() -> None:
    proc = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, check=False)
    assert REPORT.exists(), proc.stderr or proc.stdout
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for field in schema["required"]:
        assert field in report, field
    assert report["layer_id"] == "camada-testes"
    assert report["status"] in ("passed", "passed_with_warnings", "failed")
    assert report["summary"]["layers_total"] == 5


def test_all_test_layers_exist_on_disk() -> None:
    aac = json.loads(AAC.read_text(encoding="utf-8"))
    for layer_id, layer in aac["layers"].items():
        path = layer.get("path")
        assert path and (ROOT / path).exists(), f"{layer_id} missing path: {path}"


def test_living_index_references_testing_playbook() -> None:
    index_path = ROOT / "docs" / "padrao-ouro" / "living-architecture-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["tier1_docs"]["testing_playbook"] == "docs/padrao-ouro/TESTING_PLAYBOOK.md"
    assert "tests" in index["modules"]
