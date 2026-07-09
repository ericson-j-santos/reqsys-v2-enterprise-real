import importlib.util
import json
from pathlib import Path


MODULO_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_test_quality_gate.py"
SPEC = importlib.util.spec_from_file_location("validate_test_quality_gate", MODULO_PATH)
MODULO = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULO)


def test_avaliar_aprova_quando_capacidades_obrigatorias_possuem_evidencia(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_unit.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (tmp_path / "tests" / "test_api.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    politica = {
        "schema_version": "1.0.0",
        "required_capabilities": ["unit", "integration"],
        "advisory_capabilities": ["mutation"],
        "minimum_backend_coverage_percent": 60,
        "evidence_patterns": {
            "unit": ["tests/test_unit.py"],
            "integration": ["tests/test_api.py"],
            "mutation": ["**/*mutation*.yml"],
        },
    }

    relatorio = MODULO.avaliar(tmp_path, politica)

    assert relatorio["status"] == "pass"
    assert relatorio["required_missing"] == []
    assert relatorio["advisory_missing"] == ["mutation"]


def test_avaliar_reprova_quando_capacidade_obrigatoria_esta_ausente(tmp_path):
    politica = {
        "schema_version": "1.0.0",
        "required_capabilities": ["e2e"],
        "advisory_capabilities": [],
        "minimum_backend_coverage_percent": 60,
        "evidence_patterns": {"e2e": ["frontend/tests/e2e/**/*.spec.ts"]},
    }

    relatorio = MODULO.avaliar(tmp_path, politica)

    assert relatorio["status"] == "fail"
    assert relatorio["required_missing"] == ["e2e"]


def test_salvar_relatorio_gera_json_deterministico(tmp_path):
    destino = tmp_path / "artifacts" / "report.json"
    MODULO.salvar_relatorio({"status": "pass", "gate": "golden"}, destino)

    assert json.loads(destino.read_text(encoding="utf-8")) == {
        "gate": "golden",
        "status": "pass",
    }
