#!/usr/bin/env python3
"""Agent Increment Gate — bloqueia novas frentes sem incremento objetivo.

Automatiza a politica operacional:
  triagem -> ajuste minimo -> CI -> evidencia -> merge

Uso tipico (agente / Cloud Agent antes de abrir branch):
  python scripts/agent_increment_gate.py --increment-type new_front --intent "feat X"
  python scripts/agent_increment_gate.py --increment-type gap_fix --reference OPS-GAP-123
  python scripts/agent_increment_gate.py --increment-type close_duplicate --reference 405
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.coordenador_status_consolidator import (  # noqa: E402
    consolidate,
    evaluate_increment_intent,
    fetch_live_reports,
    load_json,
)

VALID_INCREMENT_TYPES = frozenset(
    {
        "new_front",
        "gap_fix",
        "close_duplicate",
        "hotfix",
        "consolidate",
    }
)


def resolve_contract_drift_count(report: dict[str, Any], explicit_path: str | None = None) -> int:
    sources = report.get("sources") or {}
    contract_governance = sources.get("contract_governance") or {}
    if contract_governance.get("semantic_drift_count") is not None:
        return int(contract_governance["semantic_drift_count"])

    semantic = contract_governance.get("semantic_diff") or {}
    if semantic.get("drift_count") is not None:
        return int(semantic["drift_count"])

    candidate_paths: list[Path] = []
    if explicit_path:
        candidate_paths.append(Path(explicit_path))
    candidate_paths.extend(
        [
            Path("artifacts/openapi/openapi-semantic-diff.json"),
            Path("artifacts/openapi/openapi-semantic-diff-strict.json"),
        ]
    )
    for path in candidate_paths:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        return int((payload.get("summary") or {}).get("drift_count") or 0)
    return 0


def load_status_report(args: argparse.Namespace) -> dict[str, Any]:
    if args.status_json:
        return load_json(Path(args.status_json))

    if args.orchestrator_json and args.health_json:
        watchdog = load_json(Path(args.watchdog_json)) if args.watchdog_json else None
        return consolidate(
            args.repo or "local/fixture",
            args.branch,
            load_json(Path(args.orchestrator_json)),
            load_json(Path(args.health_json)),
            watchdog,
        )

    if args.live:
        if not args.repo and not os.environ.get("GITHUB_REPOSITORY"):
            raise ValueError("--repo ou GITHUB_REPOSITORY e obrigatorio com --live")
        if not os.environ.get("GITHUB_TOKEN"):
            raise ValueError("GITHUB_TOKEN e obrigatorio com --live")
        repo = args.repo or os.environ["GITHUB_REPOSITORY"]
        orchestrator, health, watchdog = fetch_live_reports(
            repo,
            args.branch,
            args.run_limit,
            args.pr_limit,
            args.health_limit,
            Path(args.output_dir) / "sources" / "operational-governance-orchestrator",
            Path(args.output_dir) / "sources" / "runtime-health-validator",
            include_watchdog=True,
        )
        return consolidate(repo, args.branch, orchestrator, health, watchdog)

    raise ValueError(
        "Informe --status-json, (--orchestrator-json + --health-json) ou --live"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gate de incremento objetivo para agentes.")
    parser.add_argument(
        "--increment-type",
        required=True,
        choices=sorted(VALID_INCREMENT_TYPES),
        help="Tipo de incremento pretendido",
    )
    parser.add_argument("--reference", default="", help="OPS-GAP-*, numero de PR, etc.")
    parser.add_argument("--intent", default="", help="Descricao curta do incremento (log/evidencia)")
    parser.add_argument("--status-json", default="", help="coordenador-status.json existente")
    parser.add_argument("--orchestrator-json", default="")
    parser.add_argument("--health-json", default="")
    parser.add_argument("--watchdog-json", default="")
    parser.add_argument("--live", action="store_true", help="Consolidar ao vivo via GitHub API")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--run-limit", type=int, default=50)
    parser.add_argument("--pr-limit", type=int, default=30)
    parser.add_argument("--health-limit", type=int, default=50)
    parser.add_argument("--output-dir", default="artifacts/agent-increment-gate")
    parser.add_argument("--json", action="store_true", help="Imprimir somente JSON de decisao")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Bloqueia quando drift semantico OpenAPI > 0 (fail-closed)",
    )
    parser.add_argument(
        "--openapi-semantic-diff-json",
        default="",
        help="Caminho opcional do artifact openapi-semantic-diff.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        report = load_status_report(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    allowed, reason, detail = evaluate_increment_intent(
        report,
        args.increment_type,
        args.reference.strip(),
    )

    drift_count = resolve_contract_drift_count(
        report,
        args.openapi_semantic_diff_json.strip() or None,
    )
    strict_blocked = bool(args.strict and drift_count > 0)
    if strict_blocked:
        allowed = False
        reason = "strict_contract_drift_blocked"
        detail = (
            f"Modo --strict ativo: drift_count={drift_count}. "
            "Sincronize contrato OpenAPI e rotas backend antes de prosseguir."
        )

    payload = {
        "allowed": allowed,
        "reason": reason,
        "detail": detail,
        "strict_mode": bool(args.strict),
        "contract_drift_count": drift_count,
        "strict_blocked": strict_blocked,
        "increment_type": args.increment_type,
        "reference": args.reference or None,
        "intent": args.intent or None,
        "coordenador_state": report.get("state"),
        "coordenador_decision": report.get("decision"),
        "increment_gate": report.get("increment_gate"),
        "recommended_actions": report.get("recommended_actions", [])[:5],
        "operational_cycle": report.get("operational_cycle"),
    }

    (output_dir / "agent-increment-gate.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        status = "PERMITIDO" if allowed else "BLOQUEADO"
        print(f"[{status}] {reason}")
        if detail:
            print(detail)
        if not allowed:
            print("\nProximas acoes sugeridas:")
            for action in report.get("recommended_actions", [])[:5]:
                print(
                    f"  - {action['priority']} {action['action']} "
                    f"({action.get('reference', '')}): {action['detail']}"
                )

    return 0 if allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
