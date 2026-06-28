#!/usr/bin/env python3
"""Post-workflow evidence snapshot — Evidence Automation hook.

Consolidates pipeline governance, delivery maturity and operational artifacts
into a single auditable snapshot after CI workflows complete.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUTS = {
    "pipeline_governance": Path("artifacts/pipeline-governanca/pipeline-governanca-report.json"),
    "delivery_maturity": Path("audit/delivery-maturity/delivery-maturity-snapshot.json"),
    "runtime_health": Path("artifacts/runtime-health-center/runtime-health-report.json"),
    "ci_intelligence": Path("artifacts/operational-ci-intelligence/operational-ci-intelligence.json"),
    "coordenador_status": Path("artifacts/coordenador-status/coordenador-status.json"),
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_parse_error": True, "path": str(path)}


def compute_maturity_score(sources: dict[str, dict[str, Any] | None]) -> float:
    scores: list[float] = []
    pipeline = sources.get("pipeline_governance") or {}
    if pipeline.get("estadoGeral") == "verde":
        scores.append(95)
    elif pipeline.get("estadoGeral") == "amarelo":
        scores.append(70)
    elif pipeline:
        scores.append(40)

    runtime = sources.get("runtime_health") or {}
    if runtime.get("maturity_percent") is not None:
        scores.append(float(runtime["maturity_percent"]))

    ci = sources.get("ci_intelligence") or {}
    if ci.get("operational_score") is not None:
        scores.append(float(ci["operational_score"]))

    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 2)


def build_snapshot(sources: dict[str, dict[str, Any] | None], event: str, sha: str | None) -> dict[str, Any]:
    available = [name for name, payload in sources.items() if payload]
    maturity = compute_maturity_score(sources)
    pipeline = sources.get("pipeline_governance") or {}
    blocked = pipeline.get("estadoGeral") not in (None, "verde")
    return {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_name": event,
        "sha": sha,
        "mode": "post_workflow_hook",
        "sources_available": available,
        "sources_missing": [name for name in sources if not sources[name]],
        "maturity_score": maturity,
        "pipeline_estado_geral": pipeline.get("estadoGeral"),
        "blocked_for_promotion": blocked,
        "guardrails": [
            "report_only",
            "no_auto_merge",
            "no_deploy",
            "human_review_required",
        ],
        "inputs": {name: (payload or {"available": False}) for name, payload in sources.items()},
        "recommended_actions": [
            "Publicar artifacts faltantes antes de promover ambiente.",
            "Manter pipeline-governanca-report verde antes de merge.",
            "Consumir coordenador-status.json como leitura preferencial.",
        ] if blocked else [
            "Continuar incremento planejado com CI verde.",
            "Anexar snapshot ao PR como evidência operacional.",
        ],
    }


def render_markdown(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Post-Workflow Evidence Snapshot",
        "",
        f"- Gerado em: `{snapshot['generated_at_utc']}`",
        f"- Evento: `{snapshot['event_name']}`",
        f"- SHA: `{snapshot.get('sha') or 'local'}`",
        f"- Maturity score: `{snapshot['maturity_score']}`",
        f"- Pipeline: `{snapshot.get('pipeline_estado_geral') or 'unknown'}`",
        f"- Fontes disponíveis: `{', '.join(snapshot['sources_available']) or 'none'}`",
        "",
        "## Próximas ações",
        "",
    ]
    lines.extend(f"- {action}" for action in snapshot["recommended_actions"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate post-workflow evidence snapshot.")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/post-workflow-evidence"))
    parser.add_argument("--event", default="ci_complete")
    parser.add_argument("--sha", default=None)
    parser.add_argument("--pipeline-report", type=Path, default=DEFAULT_INPUTS["pipeline_governance"])
    args = parser.parse_args()

    sources = {
        "pipeline_governance": load_json(args.pipeline_report),
        "delivery_maturity": load_json(DEFAULT_INPUTS["delivery_maturity"]),
        "runtime_health": load_json(DEFAULT_INPUTS["runtime_health"]),
        "ci_intelligence": load_json(DEFAULT_INPUTS["ci_intelligence"]),
        "coordenador_status": load_json(DEFAULT_INPUTS["coordenador_status"]),
    }
    snapshot = build_snapshot(sources, args.event, args.sha)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "post-workflow-evidence.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "post-workflow-evidence.md").write_text(render_markdown(snapshot), encoding="utf-8")
    print(render_markdown(snapshot))
    return 1 if snapshot["blocked_for_promotion"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
