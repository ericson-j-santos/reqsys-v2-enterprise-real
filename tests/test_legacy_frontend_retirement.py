from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = REPO_ROOT / "scripts" / "check_legacy_frontend_references.py"
PHASE_2B_EVIDENCE = REPO_ROOT / "governance" / "tooling" / "e2e-consolidation-phase2b.json"
ROLLBACK_SOURCE = "ca8905ad869d857084127356cba36bb4edc69a9e"


def _checker_module():
    spec = importlib.util.spec_from_file_location("legacy_frontend_check", CHECKER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zero_referencias_operacionais_a_frontends_legados() -> None:
    checker = _checker_module()
    assert checker.find_references(REPO_ROOT) == []


def test_diretorios_legados_foram_removidos_na_fase_2b() -> None:
    checker = _checker_module()
    assert checker.find_legacy_directories(REPO_ROOT) == []
    assert not (REPO_ROOT / "frontend-angular").exists()
    assert not (REPO_ROOT / "frontend-vuetify").exists()


def test_rollback_da_fase_2b_esta_documentado() -> None:
    evidence = json.loads(PHASE_2B_EVIDENCE.read_text(encoding="utf-8"))
    assert evidence["status"] == "implemented"
    assert evidence["rollback"]["source_commit"] == ROLLBACK_SOURCE
    assert evidence["deleted_paths"] == ["frontend-angular", "frontend-vuetify"]


def test_specs_de_login_legados_foram_aposentados() -> None:
    assert not (REPO_ROOT / "e2e" / "login-angular.spec.ts").exists()
    assert not (REPO_ROOT / "e2e" / "login-vuetify.spec.ts").exists()


def test_playwright_raiz_aponta_para_suite_canonica() -> None:
    content = (REPO_ROOT / "playwright.config.ts").read_text(encoding="utf-8")
    assert "./frontend/tests/e2e" in content
    assert "./frontend" in content
    assert "frontend-canonico" in content


def test_qualidade_builda_somente_frontend_canonico() -> None:
    content = (REPO_ROOT / "scripts" / "validar_qualidade.sh").read_text(encoding="utf-8")
    assert "cd frontend" in content
    assert "login-accessibility.spec.js" in content


def test_smoke_teams_observa_servico_canonico() -> None:
    content = (
        REPO_ROOT / ".github" / "workflows" / "teams-notification-control-center-smoke.yml"
    ).read_text(encoding="utf-8")
    assert "frontend/src/services/teamsGateway.js" in content
