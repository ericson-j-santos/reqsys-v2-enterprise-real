#!/usr/bin/env python3
"""Unified Operational Signal Consolidator — fecha o loop mesh → alert → event bus.

Consolida artifacts da malha operacional, alert intelligence, event bus,
observability hub, runtime validation e coordenador em um contrato único
consumível pelo Coordenador Principal e pelo Evidence Gate consolidado.
Modo report_only: sem deploy, merge ou captura de segredos.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STATE_RANK = {"green": 0, "yellow": 1, "red": 2, "unknown": 1, "SUPPRESSED": 0, "ACTIVE": 0}

DEFAULT_INPUTS: dict[str, list[str]] = {
    "mesh_hub": [
        "artifacts/operational-runtime-mesh-hub/operational-runtime-mesh-hub.json",
    ],
    "alert_intelligence": [
        "artifacts/operational-alert-intelligence/operational-alert-intelligence.json",
    ],
    "event_bus": [
        "artifacts/unified-operational-event-bus/unified-operational-event.json",
    ],
    "observability_hub": [
        "artifacts/operational-observability-hub/operational-observability-hub.json",
    ],
    "runtime_validation": [
        "artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json",
    ],
    "coordenador_status": [
        "artifacts/coordenador-status/coordenador-status.json",
    ],
    "github_runtime_analytics": [
        "reports/github-runtime-analytics/github-runtime-analytics.json",
    ],
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_parse_error": True, "path": str(path)}


def resolve_input(paths: list[str], root: Path) -> tuple[dict[str, Any] | None, str | None]:
    for relative in paths:
        candidate = root / relative
        payload = load_json(candidate)
        if payload is not None:
            return payload, relative
    return None, None


def merge_state(*states: str) -> str:
    ranked = sorted(states, key=lambda item: STATE_RANK.get(item, 1), reverse=True)
    return ranked[0] if ranked else "unknown"


def normalize_risk(value: Any) -> str:
    raw = str(value or "unknown").strip().upper()
    mapping = {
        "LOW": "green",
        "MEDIUM": "yellow",
        "HIGH": "red",
        "INFO": "green",
        "ACTIVE": "green",
        "SUPPRESSED": "green",
        "green": "green",
        "yellow": "yellow",
        "red": "red",
    }
    return mapping.get(raw, "yellow")


def evaluate_mesh_layer(mesh: dict[str, Any] | None) -> dict[str, Any]:
    if not mesh:
        return {
            "available": False,
            "state": "yellow",
            "event_mesh": "UNKNOWN",
            "operational_risk": "unknown",
            "detail": "operational-runtime-mesh-hub ausente",
        }
    mesh_block = mesh.get("mesh") or {}
    alert = mesh.get("alert_intelligence") or {}
    hydration = mesh.get("hydration") or {}
    risk = normalize_risk(mesh_block.get("operational_risk") or alert.get("alert_level"))
    return {
        "available": True,
        "state": risk,
        "event_mesh": mesh_block.get("event_mesh", "UNKNOWN"),
        "operational_risk": mesh_block.get("operational_risk", "unknown"),
        "alert_level": alert.get("alert_level"),
        "action_policy": alert.get("action_policy"),
        "hydrated": hydration.get("enabled", False),
        "detail": f"mesh={mesh_block.get('event_mesh')} risk={mesh_block.get('operational_risk')}",
    }


def evaluate_alert_layer(alert: dict[str, Any] | None) -> dict[str, Any]:
    if not alert:
        return {
            "available": False,
            "state": "yellow",
            "should_alert": None,
            "detail": "operational-alert-intelligence ausente",
        }
    level = str(alert.get("alert_level") or "INFO")
    state = "green" if not alert.get("should_alert", True) else normalize_risk(level)
    return {
        "available": True,
        "state": state,
        "should_alert": alert.get("should_alert"),
        "alert_level": level,
        "alert_type": alert.get("alert_type"),
        "action_policy": alert.get("action_policy"),
        "detail": f"level={level} type={alert.get('alert_type')}",
    }


def evaluate_event_bus_layer(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {
            "available": False,
            "state": "yellow",
            "event_class": "UNKNOWN",
            "detail": "unified-operational-event ausente",
        }
    severity = str(event.get("severity") or "INFO")
    state = "green" if not event.get("should_emit", True) else normalize_risk(severity)
    return {
        "available": True,
        "state": state,
        "event_class": event.get("event_class"),
        "severity": severity,
        "routing_key": event.get("routing_key"),
        "action_policy": event.get("action_policy"),
        "detail": f"class={event.get('event_class')} severity={severity}",
    }


def build_cross_runtime_analytics(
    observability: dict[str, Any] | None,
    runtime_validation: dict[str, Any] | None,
    coordenador: dict[str, Any] | None,
    github_analytics: dict[str, Any] | None,
) -> dict[str, Any]:
    sources_available = sum(
        1 for item in (observability, runtime_validation, coordenador, github_analytics) if item
    )
    validation_score = (runtime_validation or {}).get("validation_score")
    coord_state = (coordenador or {}).get("state")
    hub_risk = (observability or {}).get("operational_risk")
    analytics_confidence = (github_analytics or {}).get("confidence_percent")

    scores: list[int] = []
    if isinstance(validation_score, (int, float)):
        scores.append(int(validation_score))
    if coord_state == "green":
        scores.append(90)
    elif coord_state == "yellow":
        scores.append(65)
    elif coord_state == "red":
        scores.append(30)
    if isinstance(analytics_confidence, (int, float)):
        scores.append(int(analytics_confidence))

    unified_score = round(sum(scores) / len(scores)) if scores else 50
    maturity = min(100.0, unified_score * 0.95 + sources_available * 5)

    return {
        "mode": "cross_runtime_consolidated",
        "sources_hydrated": sources_available,
        "sources_total": 4,
        "unified_score": unified_score,
        "maturity_percent": round(maturity, 1),
        "validation_score": validation_score,
        "coordenador_state": coord_state,
        "observability_risk": hub_risk,
        "github_analytics_ready": (github_analytics or {}).get("runtime_state") == "ANALYTICS_READY",
        "longitudinal_analytics": bool((observability or {}).get("longitudinal_analytics")),
        "correlation_id": (
            (observability or {}).get("correlation_id")
            or (coordenador or {}).get("correlation_id")
            or (runtime_validation or {}).get("correlation_id")
        ),
    }


def build_evidence_gate_consolidated(
    runtime_validation: dict[str, Any] | None,
    mesh_layer: dict[str, Any],
    alert_layer: dict[str, Any],
    event_layer: dict[str, Any],
) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []

    if runtime_validation:
        domain = (runtime_validation.get("domains") or {}).get("evidence_gate") or {}
        layers.append(
            {
                "id": "runtime_validation",
                "state": domain.get("state", "unknown"),
                "score": domain.get("score"),
                "detail": domain.get("detail"),
            }
        )

    if mesh_layer.get("available"):
        layers.append(
            {
                "id": "operational_mesh",
                "state": mesh_layer.get("state"),
                "detail": mesh_layer.get("detail"),
            }
        )

    if alert_layer.get("available"):
        layers.append(
            {
                "id": "alert_intelligence",
                "state": alert_layer.get("state"),
                "detail": alert_layer.get("detail"),
            }
        )

    if event_layer.get("available"):
        layers.append(
            {
                "id": "event_bus",
                "state": event_layer.get("state"),
                "detail": event_layer.get("detail"),
            }
        )

    states = [layer["state"] for layer in layers if layer.get("state")]
    consolidated_state = merge_state(*(states or ["yellow"]))
    available_layers = len(layers)
    consolidated = available_layers >= 2

    return {
        "consolidated": consolidated,
        "state": consolidated_state,
        "layers_available": available_layers,
        "layers": layers,
        "post_merge_ready": (runtime_validation or {}).get("post_merge_ready"),
        "public_runtime_ready": (runtime_validation or {}).get("public_runtime_ready"),
    }


def build_snapshot(
    repo: str,
    branch: str,
    root: Path | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    root = root or ROOT_DIR
    sources: dict[str, Any] = {}
    sources_meta: dict[str, dict[str, Any]] = {}

    for name, paths in DEFAULT_INPUTS.items():
        payload, resolved = resolve_input(paths, root)
        sources[name] = payload
        sources_meta[name] = {
            "available": payload is not None,
            "path": resolved,
            "candidates": paths,
        }

    mesh_layer = evaluate_mesh_layer(sources.get("mesh_hub"))
    alert_layer = evaluate_alert_layer(sources.get("alert_intelligence"))
    event_layer = evaluate_event_bus_layer(sources.get("event_bus"))
    cross_runtime = build_cross_runtime_analytics(
        sources.get("observability_hub"),
        sources.get("runtime_validation"),
        sources.get("coordenador_status"),
        sources.get("github_runtime_analytics"),
    )
    evidence_gate = build_evidence_gate_consolidated(
        sources.get("runtime_validation"),
        mesh_layer,
        alert_layer,
        event_layer,
    )

    mesh_integrated = all(
        layer.get("available") for layer in (mesh_layer, alert_layer, event_layer)
    )
    overall_state = merge_state(
        mesh_layer["state"],
        alert_layer["state"],
        event_layer["state"],
        evidence_gate["state"],
        *(
            [normalize_risk(cross_runtime["coordenador_state"])]
            if cross_runtime.get("coordenador_state")
            else []
        ),
    )

    maturity_percent = round(
        (
            cross_runtime["maturity_percent"] * 0.4
            + (100 if mesh_integrated else 60) * 0.3
            + (100 if evidence_gate["consolidated"] else 55) * 0.3
        ),
        1,
    )

    return {
        "schema_version": "1.0.0",
        "correlation_id": correlation_id or str(uuid4()),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": repo,
        "branch": branch,
        "mode": "report_only",
        "source": "unified-operational-signal-consolidator",
        "status": overall_state,
        "confidence_level": "HIGH" if mesh_integrated else "MEDIUM",
        "maturity_percent": maturity_percent,
        "operational_risk": overall_state,
        "commit_sha": "",
        "overall_state": overall_state,
        "mesh_integrated": mesh_integrated,
        "operational_mesh": {
            "hub": mesh_layer,
            "alert_intelligence": alert_layer,
            "event_bus": event_layer,
            "chain": "mesh_hub → alert_intelligence → event_bus → signal_consolidator",
        },
        "evidence_gate_consolidated": evidence_gate,
        "cross_runtime_analytics": cross_runtime,
        "sources": sources_meta,
        "recommended_actions": build_recommended_actions(
            mesh_integrated, evidence_gate, cross_runtime, overall_state
        ),
        "guardrails": {
            "merge": False,
            "deploy": False,
            "production_change": False,
            "report_only": True,
        },
    }


def build_recommended_actions(
    mesh_integrated: bool,
    evidence_gate: dict[str, Any],
    cross_runtime: dict[str, Any],
    overall_state: str,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if not mesh_integrated:
        actions.append(
            {
                "priority": "P0",
                "action": "completar_cadeia_mesh_operacional",
                "reference": "operational-runtime-mesh-hub",
                "detail": "Garantir artifacts mesh hub, alert intelligence e event bus na mesma execução",
            }
        )
    if not evidence_gate.get("consolidated"):
        actions.append(
            {
                "priority": "P0",
                "action": "consolidar_evidence_gate",
                "reference": "evidence_gate_consolidated",
                "detail": "Hidratar pelo menos duas camadas de evidência (runtime validation + mesh)",
            }
        )
    if cross_runtime.get("sources_hydrated", 0) < 3:
        actions.append(
            {
                "priority": "P1",
                "action": "hidratar_analytics_cross_runtime",
                "reference": f"sources={cross_runtime.get('sources_hydrated')}/4",
                "detail": "Conectar coordenador, runtime validation, observability hub e github analytics",
            }
        )
    if overall_state == "red":
        actions.append(
            {
                "priority": "P0",
                "action": "tratar_incidente_operacional_mesh",
                "reference": "unified-operational-signal",
                "detail": "Estado vermelho na malha operacional consolidada",
            }
        )
    if not actions:
        actions.append(
            {
                "priority": "P4",
                "action": "manter_malha_operacional_integrada",
                "reference": "unified-operational-signal-consolidator",
                "detail": "Cadeia mesh → alert → event bus → consolidador operacional",
            }
        )
    return actions


def render_summary(snapshot: dict[str, Any]) -> str:
    mesh = snapshot["operational_mesh"]
    evidence = snapshot["evidence_gate_consolidated"]
    analytics = snapshot["cross_runtime_analytics"]
    lines = [
        "# Unified Operational Signal Consolidator",
        "",
        f"- Correlation ID: `{snapshot['correlation_id']}`",
        f"- State: `{snapshot['overall_state']}`",
        f"- Mesh integrated: `{snapshot['mesh_integrated']}`",
        f"- Maturity: `{snapshot['maturity_percent']}%`",
        f"- Evidence gate consolidated: `{evidence['consolidated']}` (`{evidence['state']}`)",
        f"- Cross-runtime score: `{analytics['unified_score']}`",
        f"- Sources hydrated: `{analytics['sources_hydrated']}/{analytics['sources_total']}`",
        "",
        "## Operational Mesh Chain",
        "",
        f"- Hub: `{mesh['hub'].get('detail', 'n/a')}`",
        f"- Alert: `{mesh['alert_intelligence'].get('detail', 'n/a')}`",
        f"- Event bus: `{mesh['event_bus'].get('detail', 'n/a')}`",
        "",
        "## Recommended actions",
        "",
    ]
    for action in snapshot["recommended_actions"]:
        lines.append(
            f"- `{action['priority']}` · `{action['action']}` · `{action['reference']}` — {action['detail']}"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(snapshot: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "unified-operational-signal.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(render_summary(snapshot), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consolidate operational mesh signals into one artifact.")
    parser.add_argument("--repo", default="local/reqsys")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--root", type=Path, default=ROOT_DIR)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/unified-operational-signal-consolidator"),
    )
    parser.add_argument("--correlation-id", default="")
    args = parser.parse_args(argv)

    snapshot = build_snapshot(args.repo, args.branch, args.root, args.correlation_id or None)
    write_report(snapshot, args.output_dir)
    print(
        json.dumps(
            {
                "output": str(args.output_dir / "unified-operational-signal.json"),
                "overall_state": snapshot["overall_state"],
                "mesh_integrated": snapshot["mesh_integrated"],
                "evidence_gate_consolidated": snapshot["evidence_gate_consolidated"]["consolidated"],
                "maturity_percent": snapshot["maturity_percent"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
