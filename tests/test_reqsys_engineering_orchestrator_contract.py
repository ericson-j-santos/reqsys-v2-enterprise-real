import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_reqsys_engineering_orchestrator.py"
PACKAGE = ROOT / "agents" / "reqsys-engineering-orchestrator"


def run_validator(package: Path = PACKAGE) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--package-dir", str(package)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_contract_validator_passes() -> None:
    result = run_validator()
    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    assert report["checked_cases"] >= 10


def test_validation_is_idempotent() -> None:
    first = run_validator()
    second = run_validator()
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout


def test_validator_fails_closed_without_human_gate(tmp_path: Path) -> None:
    package = tmp_path / "reqsys-engineering-orchestrator"
    shutil.copytree(PACKAGE, package)

    router_path = package / "router.yaml"
    router = json.loads(router_path.read_text(encoding="utf-8"))
    router["routes"] = [item for item in router["routes"] if item["id"] != "human_gate"]
    router_path.write_text(json.dumps(router, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = run_validator(package)
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "failed"
    assert any("human_gate" in error for error in report["errors"])
