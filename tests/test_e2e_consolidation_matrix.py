from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO_ROOT / "governance" / "tooling" / "e2e-consolidation-phase1.json"


def _matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_resumo_reflete_cenarios_classificados() -> None:
    matrix = _matrix()
    scenarios = matrix["scenarios"]
    counts = Counter(item["classification"] for item in scenarios)

    assert matrix["summary"]["total_scenarios"] == len(scenarios)
    assert matrix["summary"]["migrar"] == counts["MIGRAR"]
    assert matrix["summary"]["ja_coberto"] == counts["JA_COBERTO"]
    assert matrix["summary"]["descartar"] == counts["DESCARTAR"]


def test_cenarios_migrados_possuem_destino_existente() -> None:
    matrix = _matrix()
    migrados = [item for item in matrix["scenarios"] if item["classification"] == "MIGRAR"]

    assert migrados
    for item in migrados:
        assert item.get("migration_status") == "CONCLUIDO"
        assert item.get("target")
        assert (REPO_ROOT / item["target"]).exists()


def test_arquivos_aposentados_nao_permanecem_no_repositorio() -> None:
    matrix = _matrix()

    for path in matrix["retirement"]["retired_files"]:
        assert not (REPO_ROOT / path).exists(), f"Arquivo legado ainda ativo: {path}"


def test_dependencias_legadas_restantes_estao_explicitas() -> None:
    matrix = _matrix()
    remaining = matrix["retirement"]["remaining_legacy_files"]

    assert matrix["summary"]["legacy_files_after"] == len(remaining)
    for path in remaining:
        assert (REPO_ROOT / path).exists(), f"Dependência legada declarada não existe: {path}"
