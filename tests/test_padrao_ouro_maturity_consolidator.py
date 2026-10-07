from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "padrao-ouro-maturity-consolidation.yml"


def test_delivery_maturity_snapshot_reaches_100_with_consolidated_evidence(tmp_path: Path) -> None:
  runtime_report = {
      "maturity_percent": 100,
      "domains": {
          "ci_cd": {"score": 100},
          "governance": {"score": 100},
          "environment": {"score": 100},
      },
      "gold_standard_depth": {"overall_score": 100, "axes": {"observability": {"score": 100}}},
      "ingested_artifacts": {"artifacts_available": 7, "artifacts_total": 7},
  }
  public_runtime = {
      "readiness": {
          "readiness_percent": 100,
          "operational_status": "healthy",
          "api_ready": True,
          "runtime_ready": True,
      }
  }
  trilhas = {"summary": {"gold_standard_percent": 100.0}}
  regression = {"summary": {"checks": 21, "passed": 21}}

  (tmp_path / "artifacts/runtime-health-center").mkdir(parents=True)
  (tmp_path / "audit/runtime").mkdir(parents=True)
  (tmp_path / "audit/trilhas").mkdir(parents=True)
  (tmp_path / "docs/dashboard").mkdir(parents=True)
  (tmp_path / "frontend/tests/e2e").mkdir(parents=True)
  (tmp_path / "backend/tests").mkdir(parents=True)

  (tmp_path / "artifacts/runtime-health-center/runtime-health-report.json").write_text(json.dumps(runtime_report), encoding="utf-8")
  (tmp_path / "audit/runtime/public-runtime-validation.json").write_text(json.dumps(public_runtime), encoding="utf-8")
  (tmp_path / "audit/trilhas/trilhas-padrao-ouro-report.json").write_text(json.dumps(trilhas), encoding="utf-8")
  (tmp_path / "docs/dashboard/dashboard-regression-report.json").write_text(json.dumps(regression), encoding="utf-8")
  (tmp_path / "frontend/tests/e2e/responsividade.spec.js").write_text("// e2e", encoding="utf-8")
  (tmp_path / "backend/tests/test_security_production_gates.py").write_text("# security", encoding="utf-8")

  for rel in (
      ".github/workflows/ci.yml",
      "docs/contracts/delivery-maturity-snapshot.schema.json",
      "docs/runbooks/operational-history-snapshots.md",
      ".github/workflows/operational-history-snapshot.yml",
      "AGENTS.md",
      "docs/dashboard/command-center-evidence-index.md",
      "docs/runbooks/golden-release-operational-checklist.md",
      "artifacts/public-access-validation/public-access-validation.json",
      ".github/workflows/runtime-health-center.yml",
      "docs/runbooks/runtime-operational-observability-v1.md",
      "docs/runbooks/delivery-evidence-index.md",
      "audit/runtime/public-runtime-evidence-index.json",
  ):
      path = tmp_path / rel
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text("{}", encoding="utf-8")

  sys.path.insert(0, str(ROOT))
  from scripts.delivery_maturity_snapshot import build_report

  report = build_report(tmp_path)
  assert report["average_current_percent"] == 100.0
  assert all(item["current_percent"] == 100.0 for item in report["dimensions"])


def test_padrao_ouro_maturity_consolidator_reaches_100() -> None:
  result = subprocess.run(
      [sys.executable, "scripts/padrao_ouro_maturity_consolidator.py"],
      cwd=ROOT,
      capture_output=True,
      text=True,
      check=False,
  )
  assert result.returncode == 0, result.stdout + result.stderr

  runtime = json.loads((ROOT / "artifacts/runtime-health-center/runtime-health-report.json").read_text(encoding="utf-8"))
  maturity = json.loads((ROOT / "audit/delivery-maturity/delivery-maturity-snapshot.json").read_text(encoding="utf-8"))
  health = json.loads((ROOT / "docs/ops-dashboard/data/health.json").read_text(encoding="utf-8"))
  pareto = json.loads((ROOT / "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json").read_text(encoding="utf-8"))
  readiness = json.loads((ROOT / "audit/runtime/ops-readiness-report.json").read_text(encoding="utf-8"))

  assert runtime["gold_standard_depth"]["overall_score"] == 100
  assert maturity["average_current_percent"] == 100.0
  assert health["health_score"] == 100
  assert health["public_runtime_readiness"]["readiness_percent"] == 100.0
  assert pareto["current_score"] == 100.0
  assert readiness["readiness_percent"] == 100.0


class _StubResponse:
  def __init__(self, status_code: int) -> None:
    self.status_code = status_code
    self.content = b"{}"
    self.headers: dict[str, str] = {"content-type": "application/json"}


class _StubClient:
  def get(self, endpoint: str) -> _StubResponse:
    status_code = 503 if endpoint == "/api/runtime/readiness" else 200
    return _StubResponse(status_code)


def test_in_process_runtime_validation_fails_closed_on_required_endpoint() -> None:
  from scripts.padrao_ouro_maturity_consolidator import (
      assert_required_runtime_endpoints,
      build_in_process_runtime_validation,
  )

  validation = build_in_process_runtime_validation(_StubClient())

  assert validation["validation_mode"] == "asgi_in_process"
  assert validation["network_reachability_verified"] is False
  with pytest.raises(RuntimeError, match=r"/api/runtime/readiness: 503"):
    assert_required_runtime_endpoints(validation)


def test_in_process_runtime_does_not_claim_public_reachability(monkeypatch: pytest.MonkeyPatch) -> None:
  from scripts import padrao_ouro_maturity_consolidator as consolidator

  commands: list[list[str]] = []
  monkeypatch.setattr(consolidator, "_run", lambda command: commands.append(command))

  consolidator.persist_public_runtime_evidence({"network_reachability_verified": False})

  command = commands[0]
  strict_gate_index = command.index("--strict-gate-passed")
  assert command[strict_gate_index + 1] == "false"


def test_workflow_persists_backend_virtualenv_between_steps() -> None:
  workflow = WORKFLOW.read_text(encoding="utf-8")

  assert 'echo "$PWD/.venv/bin" >> "$GITHUB_PATH"' in workflow
  assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
  assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
  assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
