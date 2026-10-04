from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_minimum_controlled_version.py"
spec = importlib.util.spec_from_file_location("validate_minimum_controlled_version", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def base_manifest():
    return {
        "reqsys_schema": "1.0",
        "version": "1.2.3",
        "maturity": "MINIMUM_CONTROLLED",
        "controls": {name: "PASS" for name in module.REQUIRED_CONTROLS},
        "contextual_controls": {
            "queue": {"status": "NOT_APPLICABLE", "justification": "fluxo síncrono"},
            "retry": "PASS",
        },
        "release_allowed": True,
    }


def test_manifesto_minimo_controlado_valido():
    assert module.validate_manifest(base_manifest()) == []


def test_falha_controle_obrigatorio_bloqueia_emissao():
    data = base_manifest()
    data["controls"]["secret_scanning"] = "FAIL"
    data["release_allowed"] = False
    errors = module.validate_manifest(data)
    assert any("maturity=MINIMUM_CONTROLLED" in item for item in errors)


def test_release_allowed_nao_pode_mentir():
    data = base_manifest()
    data["controls"]["ci"] = "FAIL"
    errors = module.validate_manifest(data)
    assert any("release_allowed inconsistente" in item for item in errors)


def test_not_applicable_exige_justificativa():
    data = base_manifest()
    data["contextual_controls"]["queue"] = {"status": "NOT_APPLICABLE", "justification": ""}
    errors = module.validate_manifest(data)
    assert any("controle contextual inválido: queue" in item for item in errors)


def test_semver_invalido_rejeitado():
    data = base_manifest()
    data["version"] = "v1"
    errors = module.validate_manifest(data)
    assert any("Versionamento Semântico" in item for item in errors)
