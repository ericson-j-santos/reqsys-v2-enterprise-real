#!/usr/bin/env python3
"""Build Merge Readiness History Index.

Agrega snapshots do gate de merge-readiness para medir retrabalho operacional:
- percentual de execuções bloqueadas;
- média de arquivos alterados por PR;
- domínios mais misturados;
- tendência de divergência de branch.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
DEFAULT_OUTPUT = "docs/ops-dashboard/data/merge-readiness-history.json"
MERGE_READINESS_WORKFLOW = "merge-readiness.yml"
MAX_SAMPLES = 60


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def workflow_runs_url() -> str:
    return f"https://github.com/{REPO}/actions/workflows/{MERGE_READINESS_WORKFLOW}"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_history(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    history = payload.get("history")
    if isinstance(history, list):
        return history
    return []


def snapshot_from_gate(
    gate: dict[str, Any],
    *,
    run_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    blocking = list(gate.get("blocking_issues") or [])
    warnings = list(gate.get("warnings") or [])
    domains = list(gate.get("domains") or [])
    return {
        "timestamp": utc_now(),
        "run_id": run_id or "",
        "correlation_id": correlation_id,
        "status": gate.get("status", "unknown"),
        "base_ref": gate.get("base_ref", "main"),
        "ahead_by": int(gate.get("ahead_by") or 0),
        "behind_by": int(gate.get("behind_by") or 0),
        "changed_files": int(gate.get("changed_files") or 0),
        "workflow_files": int(gate.get("workflow_files") or 0),
        "domains": domains,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "blocking_codes": _classify_blocking_codes(blocking),
        "workflow_run_url": (
            f"https://github.com/{REPO}/actions/runs/{run_id}" if run_id and run_id.isdigit() else workflow_runs_url()
        ),
    }


def _classify_blocking_codes(blocking_issues: list[str]) -> list[str]:
    codes: list[str] = []
    for issue in blocking_issues:
        lowered = issue.lower()
        if "atrás" in lowered or "behind" in lowered:
            codes.append("branch_behind")
        elif "conflito" in lowered or "conflict" in lowered:
            codes.append("merge_conflict")
        elif "grande demais" in lowered or "arquivos alterados" in lowered:
            codes.append("pr_too_large")
        elif "workflows" in lowered:
            codes.append("too_many_workflows")
        else:
            codes.append("other")
    return codes


def merge_history(existing: list[dict[str, Any]], snapshot: dict[str, Any], *, max_samples: int = MAX_SAMPLES) -> list[dict[str, Any]]:
    run_id = snapshot.get("run_id")
    if run_id:
        history = [item for item in existing if item.get("run_id") != run_id]
    else:
        history = list(existing)
    history.append(snapshot)
    return history[-max_samples:]


def build_metrics(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "samples": 0,
            "blocked_rate": 0.0,
            "avg_changed_files": 0.0,
            "avg_workflow_files": 0.0,
            "avg_behind_by": 0.0,
            "top_domains": [],
            "top_blocking_codes": [],
            "ready_samples": 0,
            "blocked_samples": 0,
        }

    blocked = [item for item in history if item.get("status") == "blocked"]
    domain_counter: Counter[str] = Counter()
    blocking_counter: Counter[str] = Counter()
    for item in history:
        domain_counter.update(item.get("domains") or [])
        blocking_counter.update(item.get("blocking_codes") or [])

    return {
        "samples": len(history),
        "blocked_rate": round(len(blocked) / len(history), 4),
        "avg_changed_files": round(sum(int(item.get("changed_files") or 0) for item in history) / len(history), 2),
        "avg_workflow_files": round(sum(int(item.get("workflow_files") or 0) for item in history) / len(history), 2),
        "avg_behind_by": round(sum(int(item.get("behind_by") or 0) for item in history) / len(history), 2),
        "top_domains": [
            {"domain": domain, "count": count}
            for domain, count in domain_counter.most_common(5)
        ],
        "top_blocking_codes": [
            {"code": code, "count": count}
            for code, count in blocking_counter.most_common(5)
            if code
        ],
        "ready_samples": len(history) - len(blocked),
        "blocked_samples": len(blocked),
    }


def build_payload(
    history: list[dict[str, Any]],
    *,
    merge_readiness_history_enabled: bool = True,
) -> dict[str, Any]:
    metrics = build_metrics(history)
    latest = history[-1] if history else {}
    state = "green"
    if metrics["blocked_rate"] >= 0.5:
        state = "red"
    elif metrics["blocked_rate"] > 0:
        state = "yellow"

    return {
        "schema_version": "1.0.0",
        "repo": REPO,
        "generated_at": utc_now(),
        "state": state,
        "summary": {
            "merge_readiness_history_enabled": merge_readiness_history_enabled,
            "samples": metrics["samples"],
            "blocked_rate": metrics["blocked_rate"],
            "avg_changed_files": metrics["avg_changed_files"],
            "recommendation": "reduzir_divergencia_branch" if metrics["avg_behind_by"] > 0 else "merge_readiness_estavel",
        },
        "metrics": metrics,
        "latest_snapshot": latest,
        "history": history,
        "links": {
            "workflow": workflow_runs_url(),
            "source": f"https://github.com/{REPO}/blob/main/scripts/build_merge_readiness_history.py",
            "dashboard_data": f"https://github.com/{REPO}/blob/main/{DEFAULT_OUTPUT}",
        },
        "runtime_dashboard_contract": {
            "card_fields": [
                "state",
                "blocked_rate",
                "avg_changed_files",
                "samples",
            ],
            "history_fields": [
                "timestamp",
                "status",
                "changed_files",
                "behind_by",
                "domains",
                "workflow_run_url",
            ],
            "refresh_strategy": "merge_readiness_gate_artifact_ingest",
        },
    }


def ingest_gate_report(
    report_path: str,
    output_path: str,
    *,
    run_id: str | None = None,
    correlation_id: str | None = None,
    max_samples: int = MAX_SAMPLES,
) -> dict[str, Any]:
    gate = load_json(Path(report_path))
    output = Path(output_path)
    existing = load_history(output)
    snapshot = snapshot_from_gate(gate, run_id=run_id, correlation_id=correlation_id)
    history = merge_history(existing, snapshot, max_samples=max_samples)
    payload = build_payload(history)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def write_payload(output_path: str, *, history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(history or [])
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gera merge-readiness-history.json para o dashboard operacional.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--ingest-report", help="JSON do gate merge-readiness para append no histórico")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--max-samples", type=int, default=MAX_SAMPLES)
    parser.add_argument("--json", action="store_true", help="Imprime o payload gerado")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ingest_report:
        payload = ingest_gate_report(
            args.ingest_report,
            args.output,
            run_id=args.run_id or None,
            correlation_id=args.correlation_id or None,
            max_samples=args.max_samples,
        )
    else:
        payload = write_payload(args.output)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            "merge_readiness_history_state="
            f"{payload['state']} samples={payload['summary']['samples']} output={args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
