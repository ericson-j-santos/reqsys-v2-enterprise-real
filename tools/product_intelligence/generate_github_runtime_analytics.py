#!/usr/bin/env python3
"""GitHub Runtime Analytics — analytics cross-runtime hidratado por artifacts locais."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]

ARTIFACT_CANDIDATES: dict[str, list[str]] = {
    "coordenador_status": ["artifacts/coordenador-status/coordenador-status.json"],
    "runtime_validation": [
        "artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json"
    ],
    "observability_hub": [
        "artifacts/operational-observability-hub/operational-observability-hub.json"
    ],
    "operational_mesh": [
        "artifacts/unified-operational-signal-consolidator/unified-operational-signal.json"
    ],
    "mesh_hub": [
        "artifacts/operational-runtime-mesh-hub/operational-runtime-mesh-hub.json"
    ],
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def resolve_sources(root: Path) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for name, paths in ARTIFACT_CANDIDATES.items():
        for relative in paths:
            payload = load_json(root / relative)
            if payload is not None:
                sources[name] = payload
                break
    return sources


def build_payload(root: Path) -> dict[str, Any]:
    sources = resolve_sources(root)
    coord = sources.get("coordenador_status") or {}
    validation = sources.get("runtime_validation") or {}
    hub = sources.get("observability_hub") or {}
    mesh = sources.get("operational_mesh") or {}
    mesh_hub = sources.get("mesh_hub") or {}

    scores: list[int] = []
    if isinstance(validation.get("validation_score"), (int, float)):
        scores.append(int(validation["validation_score"]))
    gold = (validation.get("gold_standard_operational_risk") or {}).get("overall_score")
    if isinstance(gold, (int, float)):
        scores.append(int(gold))
    if isinstance(coord.get("runtime_score"), (int, float)):
        scores.append(int(coord["runtime_score"]))
    cross = mesh.get("cross_runtime_analytics") or {}
    if isinstance(cross.get("unified_score"), (int, float)):
        scores.append(int(cross["unified_score"]))

    unified_score = round(sum(scores) / len(scores)) if scores else 50
    risk_percent = max(0, min(100, 100 - unified_score))
    confidence_percent = max(0, 100 - risk_percent)
    sources_hydrated = len(sources)

    runtime_state = "ANALYTICS_READY" if sources_hydrated >= 3 else "ANALYTICS_PARTIAL"
    if sources_hydrated == 0:
        runtime_state = "ANALYTICS_STUB"

    return {
        "schema_version": "1.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "cross_runtime_consolidated",
        "runtime_state": runtime_state,
        "sources": list(sources.keys()),
        "sources_hydrated": sources_hydrated,
        "sources_total": len(ARTIFACT_CANDIDATES),
        "unified_score": unified_score,
        "confidence_percent": confidence_percent,
        "risk_percent": risk_percent,
        "coordenador_state": coord.get("state"),
        "validation_score": validation.get("validation_score"),
        "mesh_integrated": mesh.get("mesh_integrated"),
        "mesh_hub_risk": (mesh_hub.get("mesh") or {}).get("operational_risk"),
        "observability_risk": hub.get("operational_risk"),
        "evidence_gate_consolidated": (validation.get("evidence_gate_consolidated") or {}).get("consolidated"),
        "correlation_id": (
            coord.get("correlation_id")
            or validation.get("correlation_id")
            or hub.get("correlation_id")
            or mesh.get("correlation_id")
        ),
        "next_recommended_increment": (
            "manter_malha_operacional_integrada"
            if runtime_state == "ANALYTICS_READY"
            else "hidratar_artifacts_cross_runtime"
        ),
    }


def write_report(payload: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "github-runtime-analytics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_lines = [
        "# GitHub Runtime Analytics",
        "",
        f"- Runtime state: {payload['runtime_state']}",
        f"- Unified score: {payload['unified_score']}",
        f"- Sources hydrated: {payload['sources_hydrated']}/{payload['sources_total']}",
        f"- Confidence: {payload['confidence_percent']}%",
        f"- Risk: {payload['risk_percent']}%",
        "",
        "## Sources",
        "",
    ]
    for source in payload["sources"]:
        md_lines.append(f"- `{source}`")
    md_lines.append("")
    (report_dir / "github-runtime-analytics.md").write_text("\n".join(md_lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate cross-runtime GitHub analytics from local artifacts")
    parser.add_argument("--root", type=Path, default=ROOT_DIR)
    parser.add_argument("--report-dir", type=Path, default=Path("reports/github-runtime-analytics"))
    args = parser.parse_args(argv)

    payload = build_payload(args.root)
    write_report(payload, args.report_dir)
    print(payload["runtime_state"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
