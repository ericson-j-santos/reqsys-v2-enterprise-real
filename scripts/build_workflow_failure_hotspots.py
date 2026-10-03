#!/usr/bin/env python3
"""Build Workflow Failure Hotspots for ReqSys.

Consolida, de forma deterministica e offline, sinais de falha recorrente em
workflows GitHub Actions a partir de um snapshot JSON local. O objetivo e
evidenciar rapidamente os 20% de workflows com maior risco de gerar retrabalho,
sem consultar rede, sem acessar secrets e sem depender da API do GitHub.

Formato aceito no input:
- lista direta de runs; ou
- objeto com chave ``workflow_runs`` / ``runs`` contendo a lista.

Campos reconhecidos por run:
- workflow_name, name, workflow, display_title ou path;
- conclusion, status;
- html_url ou url;
- created_at, updated_at ou run_started_at.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_INPUT = "artifacts/github-actions/workflow-runs.json"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/workflow-failure-hotspots.json"

FAILURE_CONCLUSIONS = {"failure", "timed_out", "action_required", "startup_failure", "cancelled"}
SUCCESS_CONCLUSIONS = {"success", "neutral", "skipped"}
ACTIVE_STATUSES = {"queued", "waiting", "requested", "in_progress", "pending"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_runs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        runs = payload.get("workflow_runs") or payload.get("runs") or []
        if isinstance(runs, list):
            return [item for item in runs if isinstance(item, dict)]
    return []


def workflow_key(run: dict[str, Any]) -> str:
    raw = (
        run.get("workflow_name")
        or run.get("name")
        or run.get("workflow")
        or run.get("display_title")
        or run.get("path")
        or "unknown"
    )
    return str(raw).strip() or "unknown"


def run_timestamp(run: dict[str, Any]) -> str:
    return str(run.get("created_at") or run.get("updated_at") or run.get("run_started_at") or "")


def is_failed(run: dict[str, Any]) -> bool:
    conclusion = str(run.get("conclusion") or "").lower()
    status = str(run.get("status") or "").lower()
    return conclusion in FAILURE_CONCLUSIONS or status in {"failure", "failed", "timed_out"}


def is_active(run: dict[str, Any]) -> bool:
    status = str(run.get("status") or "").lower()
    conclusion = str(run.get("conclusion") or "").lower()
    return status in ACTIVE_STATUSES or (status and not conclusion and status not in {"completed", "success"})


def classify_severity(failures: int, active_runs: int, total_runs: int) -> str:
    failure_ratio = failures / total_runs if total_runs else 0
    if failures >= 5 or failure_ratio >= 0.80 or active_runs >= 3:
        return "P1"
    if failures >= 2 or failure_ratio >= 0.40 or active_runs >= 1:
        return "P2"
    return "P3"


def classify_trend(failures: int, active_runs: int, total_runs: int) -> str:
    failure_ratio = failures / total_runs if total_runs else 0
    if active_runs >= 2:
        return "travado"
    if failures >= 3 or failure_ratio >= 0.60:
        return "agravando"
    if failures:
        return "monitorar"
    return "estavel"


def build_hotspots(runs: list[dict[str, Any]], limit: int = 8) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[workflow_key(run)].append(run)

    hotspots: list[dict[str, Any]] = []
    for name, items in grouped.items():
        failures = [item for item in items if is_failed(item)]
        active = [item for item in items if is_active(item)]
        successes = [
            item
            for item in items
            if str(item.get("conclusion") or "").lower() in SUCCESS_CONCLUSIONS
            or str(item.get("status") or "").lower() == "success"
        ]
        total = len(items)
        failure_ratio = round(len(failures) / total, 4) if total else 0.0
        if not failures and not active:
            continue

        latest_evidence = sorted(items, key=run_timestamp, reverse=True)[0]
        severity = classify_severity(len(failures), len(active), total)
        trend = classify_trend(len(failures), len(active), total)
        autocorrectable = severity != "P1" and len(active) < 2
        depends_on_human = severity == "P1" and len(active) >= 3

        hotspots.append(
            {
                "workflow": name,
                "severity": severity,
                "impact": "alto_retrabalho_ci" if severity == "P1" else "ruido_operacional_controlado",
                "trend": trend,
                "total_runs": total,
                "failed_runs": len(failures),
                "active_runs": len(active),
                "successful_runs": len(successes),
                "failure_ratio": failure_ratio,
                "dominant_probable_cause": (
                    "workflow_travado_sem_conclusao"
                    if len(active) >= 2
                    else "falha_recorrente_no_mesmo_workflow"
                ),
                "minimum_evidence": {
                    "latest_status": latest_evidence.get("status"),
                    "latest_conclusion": latest_evidence.get("conclusion"),
                    "latest_url": latest_evidence.get("html_url") or latest_evidence.get("url"),
                    "latest_timestamp": run_timestamp(latest_evidence),
                },
                "autocorrectable": autocorrectable,
                "depends_on_human": depends_on_human,
                "pareto_recommendation": (
                    "pausar_expansao_e_corrigir_workflow"
                    if severity == "P1"
                    else "manter_incremento_pequeno_e_adicionar_teste_de_regressao"
                ),
            }
        )

    severity_order = {"P1": 0, "P2": 1, "P3": 2}
    hotspots.sort(key=lambda item: (severity_order.get(item["severity"], 9), -item["failed_runs"], -item["active_runs"]))

    visible_hotspots = hotspots[:limit]
    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "source_path": DEFAULT_INPUT,
        "source_available": bool(runs),
        "summary": {
            "workflow_count": len(grouped),
            "hotspot_count": len(hotspots),
            "p1_count": sum(1 for item in hotspots if item["severity"] == "P1"),
            "p2_count": sum(1 for item in hotspots if item["severity"] == "P2"),
            "pareto_status": "red" if any(item["severity"] == "P1" for item in hotspots) else "yellow" if hotspots else "green",
        },
        "hotspots": visible_hotspots,
        "links": {
            "actions": f"https://github.com/{REPO}/actions",
            "pulls": f"https://github.com/{REPO}/pulls",
        },
    }


def write_output(payload: dict[str, Any], output: str) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera hotspots Pareto de falhas recorrentes em workflows.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runs = load_runs(Path(args.input))
    payload = build_hotspots(runs, limit=max(1, args.limit))
    write_output(payload, args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        summary = payload["summary"]
        print(
            f"pareto_status={summary['pareto_status']} "
            f"hotspot_count={summary['hotspot_count']} output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
