#!/usr/bin/env python3
"""Operational Runtime Mesh Hub generator.

Consolida em um único artifact as saídas antes distribuídas entre
Operational Realtime Event Mesh, Realtime Operational Mesh,
Realtime Operational Streaming Layer e Live Operational Control Center.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]

HYDRATION_CANDIDATES: dict[str, list[str]] = {
    "coordenador_status": ["artifacts/coordenador-status/coordenador-status.json"],
    "runtime_validation": [
        "artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json"
    ],
    "observability_hub": [
        "artifacts/operational-observability-hub/operational-observability-hub.json"
    ],
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def hydrate_context(root: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for name, paths in HYDRATION_CANDIDATES.items():
        for relative in paths:
            payload = _load_json(root / relative)
            if payload is not None:
                loaded[name] = payload
                break
    return loaded


def _risk_from_hydration(context: dict[str, Any]) -> str | None:
    coord = context.get("coordenador_status") or {}
    validation = context.get("runtime_validation") or {}
    hub = context.get("observability_hub") or {}

    if coord.get("state") == "red" or validation.get("overall_state") == "red":
        return "HIGH"
    if coord.get("state") == "yellow" or validation.get("overall_state") == "yellow":
        return "MEDIUM"
    risk = str(hub.get("operational_risk") or "").upper()
    if risk in {"HIGH", "MEDIUM"}:
        return risk
    if validation.get("validation_score", 0) >= 85:
        return "LOW"
    return None


def build_payload(
    source_workflow: str,
    source_conclusion: str,
    *,
    hydration_context: dict[str, Any] | None = None,
) -> dict:
    alert_level = "INFO"
    alert_type = "OPERATIONAL_SIGNAL"
    action_policy = "OBSERVE"
    operational_risk = "LOW"
    stream_status = "ACTIVE"

    if source_conclusion not in {"", "success"}:
        alert_level = "MEDIUM"
        alert_type = "SOURCE_DEGRADED"
        action_policy = "MANUAL_REVIEW_REQUIRED"
        operational_risk = "MEDIUM"
    if source_conclusion == "cancelled":
        alert_level = "LOW"
        alert_type = "CANCELLED_RUN"
        action_policy = "VERIFY_CONTEXT"

    hydration_context = hydration_context or {}
    hydrated_risk = _risk_from_hydration(hydration_context)
    if hydrated_risk == "HIGH":
        operational_risk = "HIGH"
        alert_level = "HIGH"
        action_policy = "MANUAL_REVIEW_REQUIRED"
    elif hydrated_risk == "MEDIUM" and operational_risk == "LOW":
        operational_risk = "MEDIUM"
        alert_level = "MEDIUM"

    validation = hydration_context.get("runtime_validation") or {}
    coord = hydration_context.get("coordenador_status") or {}
    hub = hydration_context.get("observability_hub") or {}
    realtime_readiness = "99%"
    if validation.get("validation_score") is not None:
        realtime_readiness = f"{min(100, int(validation['validation_score']))}%"

    return {
        "schema_version": "1.0.0",
        "hub": "operational-runtime-mesh-hub",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "consolidation": {
            "supersedes": [
                "Operational Realtime Event Mesh",
                "Realtime Operational Mesh",
                "Realtime Operational Streaming Layer",
                "Live Operational Control Center",
            ],
            "mode": "governed_consolidation",
        },
        "source": {
            "workflow": source_workflow,
            "conclusion": source_conclusion,
        },
        "hydration": {
            "enabled": bool(hydration_context),
            "coordenador_state": coord.get("state"),
            "validation_score": validation.get("validation_score"),
            "observability_status": hub.get("status"),
        },
        "mesh": {
            "event_mesh": stream_status,
            "streaming_layer": "INITIALIZED",
            "control_center": "OPERATIONAL",
            "operational_risk": operational_risk,
            "realtime_readiness": realtime_readiness,
        },
        "alert_intelligence": {
            "alert_level": alert_level,
            "alert_type": alert_type,
            "noise_level": "LOW",
            "action_policy": action_policy,
            "notification_suppressed": alert_level == "INFO",
        },
        "governance": {
            "cascade_prevention": True,
            "false_notification_guard": True,
            "mandatory_ci_gates_preserved": True,
        },
    }


def render_markdown(payload: dict) -> str:
    source = payload["source"]
    mesh = payload["mesh"]
    alert = payload["alert_intelligence"]
    return "\n".join(
        [
            "# Operational Runtime Mesh Hub",
            "",
            f"- Source workflow: `{source['workflow']}`",
            f"- Source conclusion: `{source['conclusion']}`",
            f"- Event mesh: `{mesh['event_mesh']}`",
            f"- Control center: `{mesh['control_center']}`",
            f"- Operational risk: `{mesh['operational_risk']}`",
            f"- Alert level: `{alert['alert_level']}`",
            f"- Action policy: `{alert['action_policy']}`",
            f"- Notification suppressed: `{alert['notification_suppressed']}`",
            "",
            "## Consolidation",
            "",
            "Este hub substitui a cascata entre workflows mesh redundantes.",
            "Falhas aqui são informativas, salvo degradação da fonte primária.",
        ]
    )


def render_html(payload: dict) -> str:
    source = payload["source"]
    mesh = payload["mesh"]
    alert = payload["alert_intelligence"]
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Operational Runtime Mesh Hub</title>
<style>
body{{font-family:Arial,sans-serif;background:#020617;color:#e2e8f0;margin:0;padding:24px}}
.container{{max-width:1500px;margin:0 auto}}
.title{{font-size:32px;font-weight:bold;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}
.card{{background:#111827;border:1px solid #1f2937;border-radius:16px;padding:20px}}
.metric{{font-size:34px;font-weight:bold;color:#22c55e;margin-top:8px}}
.label{{color:#94a3b8;font-size:14px}}
</style>
</head>
<body>
<div class="container">
<div class="title">Operational Runtime Mesh Hub</div>
<div class="grid">
<div class="card"><div class="label">Source</div><div class="metric">{source['workflow']}</div></div>
<div class="card"><div class="label">Event Mesh</div><div class="metric">{mesh['event_mesh']}</div></div>
<div class="card"><div class="label">Risk</div><div class="metric">{mesh['operational_risk']}</div></div>
<div class="card"><div class="label">Alert</div><div class="metric">{alert['alert_level']}</div></div>
</div>
</div>
</body>
</html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operational Runtime Mesh Hub generator")
    parser.add_argument("--source-workflow", default="manual")
    parser.add_argument("--source-conclusion", default="success")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-runtime-mesh-hub"))
    parser.add_argument("--root", type=Path, default=ROOT_DIR, help="Repo root for artifact hydration")
    parser.add_argument("--no-hydrate", action="store_true", help="Skip local artifact hydration")
    args = parser.parse_args(argv)

    hydration_context = {} if args.no_hydrate else hydrate_context(args.root)
    payload = build_payload(
        args.source_workflow,
        args.source_conclusion,
        hydration_context=hydration_context,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)

    (args.out_dir / "operational-runtime-mesh-hub.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "operational-runtime-mesh-hub.md").write_text(render_markdown(payload), encoding="utf-8")
    (args.out_dir / "operational-runtime-mesh-hub.html").write_text(render_html(payload), encoding="utf-8")

    print(f"Operational Runtime Mesh Hub: {payload['mesh']['event_mesh']} risk={payload['mesh']['operational_risk']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
