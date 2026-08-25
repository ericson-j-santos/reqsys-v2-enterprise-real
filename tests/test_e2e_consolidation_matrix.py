from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = REPO_ROOT / "governance" / "tooling" / "e2e-consolidation-phase1.json"
PHASE2A_PATH = REPO_ROOT / "governance" / "tooling" / "e2e-consolidation-phase2a.json"


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


def test_dependencias_restantes_da_fase1_foram_tratadas_na_fase2a() -> None:
    matrix = _matrix()
    remaining = set(matrix["retirement"]["remaining_legacy_files"])

    assert matrix["summary"]["legacy_files_after"] == len(remaining)
    assert PHASE2A_PATH.exists(), "Fase 2A deve registrar o destino das dependências remanescentes"

    phase2a = json.loads(PHASE2A_PATH.read_text(encoding="utf-8"))
    retired_later = set(phase2a["retired_legacy_specs"])

    assert remaining <= retired_later
    for path in remaining:
        assert not (REPO_ROOT / path).exists(), f"Spec legado ainda ativo após Fase 2A: {path}"
