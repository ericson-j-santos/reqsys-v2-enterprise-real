#!/usr/bin/env python3
"""Operational Center History P0.

Creates and analyzes operational snapshots from the Operational Intelligence Hub.
The engine is file/artifact based and does not require an external database.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def minutes_between(start: Any, end: Any) -> float | None:
    start_dt = parse_dt(start)
    end_dt = parse_dt(end)
    if not start_dt or not end_dt:
        return None
    return round((end_dt - start_dt).total_seconds() / 60, 2)


def build_snapshot(hub: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    score = hub.get("hub_score", {})
    workflow_totals: Counter[str] = Counter()
    workflow_failures: Counter[str] = Counter()
    workflow_success: Counter[str] = Counter()
    durations: list[float] = []
    mttr_candidates: list[float] = []

    grouped_by_workflow: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        workflow = str(run.get("workflowName") or run.get("name") or "unknown")
        conclusion = str(run.get("conclusion") or "unknown")
        workflow_totals[workflow] += 1
        grouped_by_workflow[workflow].append(run)
        if conclusion == "success":
            workflow_success[workflow] += 1
        elif conclusion in {"failure", "timed_out", "action_required"}:
            workflow_failures[workflow] += 1
        duration = minutes_between(run.get("createdAt") or run.get("created_at"), run.get("updatedAt") or run.get("updated_at"))
        if duration is not None and duration >= 0:
            durations.append(duration)

    for workflow, items in grouped_by_workflow.items():
        ordered = sorted(items, key=lambda item: str(item.get("createdAt") or item.get("created_at") or ""))
        last_failure_time = None
        for item in ordered:
            conclusion = str(item.get("conclusion") or "unknown")
            created = item.get("createdAt") or item.get("created_at")
            if conclusion in {"failure", "timed_out", "action_required"}:
                last_failure_time = created
            elif conclusion == "success" and last_failure_time:
                recovery = minutes_between(last_failure_time, created)
                if recovery is not None and recovery >= 0:
                    mttr_candidates.append(recovery)
                last_failure_time = None

    workflow_rates = []
    for workflow, total in workflow_totals.items():
        failures = workflow_failures[workflow]
        successes = workflow_success[workflow]
        workflow_rates.append(
            {
                "workflow": workflow,
                "total": total,
                "success": successes,
                "failure": failures,
                "failure_rate_percent": round((failures / total) * 100, 2) if total else 0,
                "success_rate_percent": round((successes / total) * 100, 2) if total else 0,
            }
        )

    workflow_rates.sort(key=lambda item: (item["failure_rate_percent"], item["total"]), reverse=True)

    return {
        "schema_version": "1.0.0",
        "snapshot_at_utc": generated_at,
        "hub_status": score.get("status", "SEM_DADOS"),
        "hub_score": score.get("score", 0),
        "hub_confidence": score.get("confidence", "baixa"),
        "runs_analyzed": len(runs),
        "workflow_failure_rates": workflow_rates,
        "metrics": {
            "avg_run_duration_minutes": round(sum(durations) / len(durations), 2) if durations else 0,
            "mttr_minutes": round(sum(mttr_candidates) / len(mttr_candidates), 2) if mttr_candidates else None,
            "workflows_with_failures": sum(1 for item in workflow_rates if item["failure"] > 0),
            "overall_failure_rate_percent": round((sum(workflow_failures.values()) / sum(workflow_totals.values())) * 100, 2) if workflow_totals else 0,
        },
        "recommendations": hub.get("recommendations", []),
        "blocked_actions": hub.get("blocked_actions", []),
    }


def merge_history(existing: list[dict[str, Any]], snapshot: dict[str, Any], max_items: int) -> list[dict[str, Any]]:
    merged = [item for item in existing if isinstance(item, dict)]
    merged.append(snapshot)
    merged.sort(key=lambda item: str(item.get("snapshot_at_utc", "")))
    return merged[-max_items:]


def calculate_trend(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {"status": "SEM_DADOS", "direction": "unknown", "delta_score": 0, "points": 0}
    scores = [float(item.get("hub_score") or 0) for item in history]
    first = scores[0]
    last = scores[-1]
    delta = round(last - first, 2)
    if delta > 2:
        direction = "melhorando"
    elif delta < -2:
        direction = "piorando"
    else:
        direction = "estavel"
    return {
        "status": history[-1].get("hub_status", "SEM_DADOS"),
        "direction": direction,
        "delta_score": delta,
        "points": len(history),
        "first_score": first,
        "last_score": last,
        "avg_score": round(sum(scores) / len(scores), 2),
    }


def render_markdown(snapshot: dict[str, Any], trend: dict[str, Any], history: list[dict[str, Any]]) -> str:
    lines = [
        "# Operational Center History",
        "",
        f"Atualizado em UTC: `{snapshot['snapshot_at_utc']}`",
        "",
        "## Estado atual",
        "",
        f"- Status: `{snapshot['hub_status']}`",
        f"- Score: `{snapshot['hub_score']}%`",
        f"- Confiança: `{snapshot['hub_confidence']}`",
        f"- Runs analisados: `{snapshot['runs_analyzed']}`",
        f"- Taxa geral de falha: `{snapshot['metrics']['overall_failure_rate_percent']}%`",
        f"- Duração média: `{snapshot['metrics']['avg_run_duration_minutes']} min`",
        f"- MTTR estimado: `{snapshot['metrics']['mttr_minutes']}`",
        "",
        "## Tendência",
        "",
        f"- Direção: `{trend['direction']}`",
        f"- Delta score: `{trend['delta_score']}`",
        f"- Pontos históricos: `{trend['points']}`",
        f"- Score médio: `{trend.get('avg_score', 0)}`",
        "",
        "## Workflows por taxa de falha",
        "",
        "| Workflow | Total | Sucesso | Falha | Taxa de falha |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in snapshot.get("workflow_failure_rates", [])[:15]:
        lines.append(
            f"| {item['workflow']} | {item['total']} | {item['success']} | {item['failure']} | {item['failure_rate_percent']}% |"
        )
    lines.extend(["", "## Últimos snapshots", "", "| Data UTC | Status | Score | Falha geral | MTTR |", "|---|---|---:|---:|---:|"])
    for item in history[-10:]:
        metrics = item.get("metrics", {})
        lines.append(
            f"| {item.get('snapshot_at_utc')} | {item.get('hub_status')} | {item.get('hub_score')} | {metrics.get('overall_failure_rate_percent')}% | {metrics.get('mttr_minutes')} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_html(snapshot: dict[str, Any], trend: dict[str, Any], history: list[dict[str, Any]]) -> str:
    rows = "".join(
        f"<tr><td>{item['workflow']}</td><td>{item['total']}</td><td>{item['success']}</td><td>{item['failure']}</td><td>{item['failure_rate_percent']}%</td></tr>"
        for item in snapshot.get("workflow_failure_rates", [])[:20]
    )
    history_rows = "".join(
        f"<tr><td>{item.get('snapshot_at_utc')}</td><td>{item.get('hub_status')}</td><td>{item.get('hub_score')}%</td><td>{item.get('metrics', {}).get('overall_failure_rate_percent')}%</td><td>{item.get('metrics', {}).get('mttr_minutes')}</td></tr>"
        for item in history[-20:]
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ReqSys Operational History</title>
<style>
body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#0f172a;color:#e5e7eb}}main{{max-width:1200px;margin:auto;padding:24px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.card{{background:#111827;border:1px solid #374151;border-radius:16px;padding:18px}}.value{{font-size:28px;font-weight:800}}.muted{{color:#9ca3af}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #374151;text-align:left}}th{{color:#9ca3af}}.ok{{color:#22c55e}}.warn{{color:#f59e0b}}.bad{{color:#ef4444}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>ReqSys Operational History</h1><p class="muted">Histórico operacional baseado em snapshots auditáveis.</p>
<section class="grid">
<div class="card"><div class="muted">Status</div><div class="value">{snapshot['hub_status']}</div></div>
<div class="card"><div class="muted">Score</div><div class="value">{snapshot['hub_score']}%</div></div>
<div class="card"><div class="muted">Tendência</div><div class="value">{trend['direction']}</div></div>
<div class="card"><div class="muted">MTTR</div><div class="value">{snapshot['metrics']['mttr_minutes']}</div></div>
</section>
<section class="card" style="margin-top:16px"><h2>Workflows por taxa de falha</h2><table><thead><tr><th>Workflow</th><th>Total</th><th>Sucesso</th><th>Falha</th><th>Taxa</th></tr></thead><tbody>{rows}</tbody></table></section>
<section class="card" style="margin-top:16px"><h2>Últimos snapshots</h2><table><thead><tr><th>Data UTC</th><th>Status</th><th>Score</th><th>Falha geral</th><th>MTTR</th></tr></thead><tbody>{history_rows}</tbody></table></section>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Operational Center historical snapshots and trend report.")
    parser.add_argument("--hub", type=Path, default=Path("artifacts/operational-intelligence-hub/operational-intelligence-hub.json"))
    parser.add_argument("--runs", type=Path, default=Path("artifacts/operational-health/runs.json"))
    parser.add_argument("--history", type=Path, default=Path("data/operational-history/history.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-history"))
    parser.add_argument("--max-items", type=int, default=120)
    args = parser.parse_args()

    hub = load_json(args.hub, {})
    runs = load_json(args.runs, [])
    if isinstance(runs, dict):
        runs = runs.get("workflow_runs") or runs.get("runs") or []
    existing = load_json(args.history, [])
    snapshot = build_snapshot(hub, runs if isinstance(runs, list) else [])
    history = merge_history(existing if isinstance(existing, list) else [], snapshot, args.max_items)
    trend = calculate_trend(history)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "operational-history-snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "operational-history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "operational-history-trend.json").write_text(json.dumps(trend, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / "operational-history.md").write_text(render_markdown(snapshot, trend, history), encoding="utf-8")
    (args.out_dir / "operational-history.html").write_text(render_html(snapshot, trend, history), encoding="utf-8")
    print(render_markdown(snapshot, trend, history))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
