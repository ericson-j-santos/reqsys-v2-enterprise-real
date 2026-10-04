"""Garante que o backlog Pareto canônico seja acionável pelo Agent Increment Gate.

Sem espelhamento, `agent_increment_gate.py --increment-type gap_fix --reference OPS-GAP-*`
bloqueia qualquer correção dos gaps P0/P1 da matriz enterprise.
"""
import json
from pathlib import Path

from scripts.coordenador_status_consolidator import evaluate_increment_intent

MATRIX = Path("docs/padrao-ouro/enterprise-gap-closure-matrix.json")
REGISTRY = Path("config/operational-gaps-registry.json")
REPORT = {
    "increment_gate": {"allowed_increment_types": ["gap_fix", "hotfix", "consolidate"]},
    "automatic_backlog": [],
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_canonical_pareto_gap_is_registered():
    matrix_ids = {gap["id"] for gap in load(MATRIX)["gaps"]}
    registry_ids = {gap["id"] for gap in load(REGISTRY)["gaps"]}
    assert matrix_ids <= registry_ids, sorted(matrix_ids - registry_ids)


def test_registered_pareto_gaps_keep_matrix_metadata():
    matrix = {gap["id"]: gap for gap in load(MATRIX)["gaps"]}
    for gap in load(REGISTRY)["gaps"]:
        canonical = matrix.get(gap["id"])
        if not canonical:
            continue
        assert gap["priority"] == canonical["priority"]
        assert gap["scope"] == canonical["pillar"]
        assert gap["reference_document"] == str(MATRIX)
        assert "gap_fix" in gap["allowed_increment_types"]


def test_increment_gate_accepts_canonical_p0_references():
    for gap in load(MATRIX)["gaps"]:
        if gap["priority"] != "P0":
            continue
        allowed, reason, _ = evaluate_increment_intent(REPORT, "gap_fix", gap["id"])
        assert allowed, f"{gap['id']} bloqueado: {reason}"


def test_increment_gate_still_rejects_unknown_reference():
    allowed, reason, _ = evaluate_increment_intent(REPORT, "gap_fix", "OPS-GAP-INEXISTENTE-999")
    assert not allowed and reason == "gap_fix_invalido"
