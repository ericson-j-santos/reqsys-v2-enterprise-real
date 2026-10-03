from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "generate_evidence_dashboard.py"
SPEC = importlib.util.spec_from_file_location("gitlab_evidence_dashboard", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dashboard_sem_nenhum_artefato_fica_sem_evidencia(tmp_path: Path) -> None:
    dashboard = MODULE.montar_dashboard(tmp_path)

    assert dashboard["status_geral"] == "sem_evidencia"
    assert all(cartao["status"] == "sem_evidencia" for cartao in dashboard["cartoes"])
    assert len(dashboard["cartoes"]) == 6


def test_dashboard_gate_falho_marca_status_geral_como_erro(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "gitlab-operational-evidence.json",
        {
            "status": "failed",
            "checks": [
                {"name": "pipeline_real", "passed": True, "detail": "ok"},
                {"name": "security_scanners", "passed": False, "detail": "missing=backend_sast_bandit"},
            ],
        },
    )

    dashboard = MODULE.montar_dashboard(tmp_path)

    assert dashboard["status_geral"] == "erro"
    gate_cartoes = [c for c in dashboard["cartoes"] if c["fonte"] == "gitlab-operational-evidence.json"]
    assert len(gate_cartoes) == 2
    assert any(c["status"] == "erro" for c in gate_cartoes)


def test_dashboard_todos_os_scanners_limpos_fica_ok(tmp_path: Path) -> None:
    _write_json(tmp_path / "gitlab-bandit-report.json", {"results": []})
    _write_json(tmp_path / "gitlab-pip-audit-report.json", [])
    _write_json(tmp_path / "gitlab-npm-audit-report.json", {"metadata": {"vulnerabilities": {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0}}})
    _write_json(tmp_path / "gitlab-trivy-report.json", {"Results": []})
    _write_json(tmp_path / "gitlab-secret-detection-report.json", [])

    dashboard = MODULE.montar_dashboard(tmp_path)

    scanners = [c for c in dashboard["cartoes"] if c["fonte"] != "validate_gitlab_operational_evidence.py" and c["fonte"] != "gitlab-operational-evidence.json"]
    assert all(cartao["status"] == "ok" for cartao in scanners)


def test_dashboard_bandit_com_achado_high_marca_erro(tmp_path: Path) -> None:
    _write_json(tmp_path / "gitlab-bandit-report.json", {"results": [{"issue_severity": "HIGH"}]})

    dashboard = MODULE.montar_dashboard(tmp_path)

    bandit = next(c for c in dashboard["cartoes"] if c["fonte"] == "backend_sast_bandit")
    assert bandit["status"] == "erro"


def test_dashboard_gitleaks_com_segredo_marca_erro(tmp_path: Path) -> None:
    _write_json(tmp_path / "gitlab-secret-detection-report.json", [{"RuleID": "generic-api-key"}])

    dashboard = MODULE.montar_dashboard(tmp_path)

    gitleaks = next(c for c in dashboard["cartoes"] if c["fonte"] == "secret_detection_gitleaks")
    assert gitleaks["status"] == "erro"
    assert "1 segredos" in gitleaks["detalhe"]


def test_render_html_e_autocontido_sem_cdn_externo(tmp_path: Path) -> None:
    dashboard = MODULE.montar_dashboard(tmp_path)

    pagina = MODULE.render_html(dashboard)

    assert "<html" in pagina
    assert "http://" not in pagina
    assert "https://" not in pagina
    assert "cdn." not in pagina


def test_write_outputs_gera_html_e_json(tmp_path: Path) -> None:
    dashboard = MODULE.montar_dashboard(tmp_path)
    saida = tmp_path / "saida"

    MODULE.write_outputs(dashboard, saida)

    assert (saida / "gitlab-evidence-dashboard.html").exists()
    conteudo_json = json.loads((saida / "gitlab-evidence-dashboard.json").read_text(encoding="utf-8"))
    assert conteudo_json["status_geral"] == dashboard["status_geral"]
