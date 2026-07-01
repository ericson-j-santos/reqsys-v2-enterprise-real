#!/usr/bin/env python3
"""Padrão Ouro Operational Consolidator.

Gera um snapshot determinístico de prontidão operacional a partir do
`coordenador-status.json` e dos artefatos Tier 1. O objetivo é transformar
pedidos amplos de consolidação em uma decisão objetiva: consolidado, em
consolidação ou bloqueado, com próximas ações rastreáveis.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATUS_JSON = "artifacts/coordenador-status/coordenador-status.json"
DEFAULT_OUTPUT = "artifacts/padrao-ouro-operational-consolidator/padrao-ouro-operational-consolidator.json"

TIER1_ARTIFACTS = {
    "hub": "docs/padrao-ouro/README.md",
    "living_architecture_index": "docs/padrao-ouro/LIVING_ARCHITECTURE_INDEX.md",
    "living_architecture_index_json": "docs/padrao-ouro/living-architecture-index.json",
    "adr_index": "docs/padrao-ouro/ADR_INDEX.md",
    "runtime_evidence_graph": "docs/padrao-ouro/RUNTIME_EVIDENCE_GRAPH.md",
    "contract_catalog": "docs/padrao-ouro/CONTRACT_CATALOG.md",
    "engineering_playbooks": "docs/padrao-ouro/ENGINEERING_PLAYBOOKS.md",
    "testing_playbook": "docs/padrao-ouro/TESTING_PLAYBOOK.md",
    "foco_padrao_ouro": "docs/padrao-ouro/FOCO_PADRAO_OURO.md",
}

REQUIRED_CYCLE = ["triagem", "ajuste_minimo", "ci_completo", "evidencia", "merge_controlado"]
ALLOWED_DURING_YELLOW = {"gap_fix", "hotfix", "consolidate", "close_duplicate"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def tier1_status(root: Path) -> dict[str, Any]:
    items: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for key, relative in TIER1_ARTIFACTS.items():
        path = root / relative
        exists = path.exists() and path.is_file()
        items[key] = {"path": relative, "exists": exists}
        if not exists:
            missing.append(relative)
    return {"complete": not missing, "missing": missing, "items": items}


def _status_action(status: dict[str, Any]) -> dict[str, str] | None:
    if status:
        return None
    return {
        "priority": "P0",
        "action": "publicar_coordenador_status_evidence",
        "detail": "Gerar ou baixar artifacts/coordenador-status/coordenador-status.json antes de promover ou abrir nova frente.",
    }


def _tier1_action(missing: list[str]) -> dict[str, str] | None:
    if not missing:
        return None
    return {
        "priority": "P1",
        "action": "restaurar_artefatos_tier1",
        "detail": "Artefatos Padrão Ouro ausentes: " + ", ".join(missing),
    }


def _cycle_action(missing: list[str]) -> dict[str, str] | None:
    if not missing:
        return None
    return {
        "priority": "P0",
        "action": "completar_ciclo_operacional",
        "detail": "Etapas ausentes no ciclo operacional: " + ", ".join(missing),
    }


def evaluate(status: dict[str, Any], tier1: dict[str, Any]) -> dict[str, Any]:
    state = str(status.get("state") or "unknown").lower()
    increment_gate = status.get("increment_gate") if isinstance(status.get("increment_gate"), dict) else {}
    allowed_types = set(increment_gate.get("allowed_increment_types") or [])
    blockers = list(increment_gate.get("blockers") or [])
    operational_cycle = list(status.get("operational_cycle") or [])
    missing_cycle = [step for step in REQUIRED_CYCLE if step not in operational_cycle]
    summary = status.get("summary") if isinstance(status.get("summary"), dict) else {}

    status_available = bool(status)
    tier1_complete = bool(tier1.get("complete"))
    new_front_allowed = bool(increment_gate.get("new_front_allowed"))
    consolidation_lane_available = "consolidate" in allowed_types
    yellow_policy_ok = state != "yellow" or allowed_types.issubset(ALLOWED_DURING_YELLOW)

    hard_blockers: list[str] = []
    if not status_available:
        hard_blockers.append("coordenador_status_missing")
    if state == "red":
        hard_blockers.append("coordenador_state_red")
    if int(summary.get("critical_gaps") or 0) > 0:
        hard_blockers.append("critical_gaps_open")
    if int(summary.get("red_workflows") or 0) > 0:
        hard_blockers.append("red_workflows")
    if int(summary.get("missing_critical_workflows") or 0) > 0:
        hard_blockers.append("missing_critical_workflows")
    if missing_cycle:
        hard_blockers.append("operational_cycle_incomplete")
    if not tier1_complete:
        hard_blockers.append("tier1_artifacts_missing")
    if state == "yellow" and not consolidation_lane_available:
        hard_blockers.append("consolidation_lane_unavailable")
    if state == "yellow" and not yellow_policy_ok:
        hard_blockers.append("yellow_state_allows_new_front")

    if not hard_blockers and state == "green" and new_front_allowed:
        readiness = "gold"
        decision = "operacional_padrao_ouro_consolidado"
        next_increment_type = "new_front"
    elif not hard_blockers and state in {"green", "yellow"} and consolidation_lane_available:
        readiness = "consolidating"
        decision = "consolidar_evidencias_antes_de_nova_frente"
        next_increment_type = "consolidate"
    else:
        readiness = "blocked"
        decision = "bloquear_incremento_ate_corrigir_gaps_operacionais"
        next_increment_type = "gap_fix" if "critical_gaps_open" in hard_blockers else "consolidate"

    actions = [
        action
        for action in (
            _status_action(status),
            _tier1_action(list(tier1.get("missing") or [])),
            _cycle_action(missing_cycle),
        )
        if action is not None
    ]
    if state == "yellow" and consolidation_lane_available:
        actions.append(
            {
                "priority": "P1",
                "action": "manter_modo_consolidacao",
                "detail": "Executar Agent Increment Gate com --increment-type consolidate e anexar evidência no PR.",
            }
        )
    actions.extend(status.get("recommended_actions") or [])

    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "readiness": readiness,
        "decision": decision,
        "next_increment_type": next_increment_type,
        "coordenador_state": state,
        "coordenador_decision": status.get("decision"),
        "new_front_allowed": new_front_allowed,
        "consolidation_lane_available": consolidation_lane_available,
        "hard_blockers": hard_blockers,
        "coordenador_blockers": blockers,
        "operational_cycle": operational_cycle,
        "missing_operational_cycle_steps": missing_cycle,
        "tier1": tier1,
        "summary": {
            "open_prs": int(summary.get("open_prs") or 0),
            "critical_gaps": int(summary.get("critical_gaps") or 0),
            "red_workflows": int(summary.get("red_workflows") or 0),
            "pending_workflows": int(summary.get("pending_workflows") or 0),
            "missing_critical_workflows": int(summary.get("missing_critical_workflows") or 0),
        },
        "recommended_actions": actions[:10],
    }


def write_report(report: dict[str, Any], output: str | Path) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consolida prontidão operacional Padrão Ouro.")
    parser.add_argument("--status-json", default=DEFAULT_STATUS_JSON, help="Caminho do coordenador-status.json.")
    parser.add_argument("--repo-root", default=".", help="Raiz do repositório para validar artefatos Tier 1.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Arquivo JSON de saída.")
    parser.add_argument("--json", action="store_true", help="Imprime o relatório JSON no stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.repo_root)
    report = evaluate(load_json(args.status_json), tier1_status(root))
    write_report(report, args.output)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(
            " ".join(
                [
                    f"readiness={report['readiness']}",
                    f"decision={report['decision']}",
                    f"next_increment_type={report['next_increment_type']}",
                    f"hard_blockers={len(report['hard_blockers'])}",
                ]
            )
        )
    return 0 if report["readiness"] in {"gold", "consolidating"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
