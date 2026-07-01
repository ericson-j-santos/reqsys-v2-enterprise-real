#!/usr/bin/env python3
"""Conflict Prediction Gate.

Classifica risco de conflito de um PR a partir de paths alterados e sinais
deterministicos. Primeira versao sem IA para manter reprodutibilidade em CI.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HIGH_RISK_PREFIXES = (
    ".github/workflows/",
    "backend/app/main.py",
    "backend/app/api/",
    "backend/app/runtime/",
    "frontend/src/router/",
    "frontend/src/layouts/",
    "fly.toml",
    "docker-compose",
)

MEDIUM_RISK_PREFIXES = (
    "backend/tests/",
    "frontend/src/services/",
    "frontend/src/views/",
    "tests/",
)

LOW_RISK_PREFIXES = (
    "docs/",
    "artifacts/",
)

CONTRACT_HINTS = (
    "schema",
    "contract",
    "openapi",
    "api/",
    "router",
    "migration",
)

WORKFLOW_PREFIX = ".github/workflows/"

RISK_COLORS = {
    "low": "green",
    "medium": "green",
    "high": "yellow",
    "blocked": "red",
}

CAPACITY_BY_RISK = {
    "low": 5,
    "medium": 3,
    "high": 1,
    "blocked": 0,
}

NEXT_ACTION_BY_RISK = {
    "low": "continuar_incrementos_paralelos",
    "medium": "continuar_com_limite_de_capacidade",
    "high": "serializar_merge_com_revisao",
    "blocked": "bloquear_merge_e_resolver_conflito",
}


def load_paths(raw_paths: list[str], paths_file: str | None = None) -> list[str]:
    paths = [item.strip() for item in raw_paths if item.strip()]
    if paths_file:
        file_path = Path(paths_file)
        if file_path.exists():
            paths.extend(item.strip() for item in file_path.read_text(encoding="utf-8").splitlines() if item.strip())
    return sorted(dict.fromkeys(paths))


def load_optional_paths(paths_file: str | None = None) -> list[str]:
    if not paths_file:
        return []
    file_path = Path(paths_file)
    if not file_path.exists():
        return []
    return sorted(
        dict.fromkeys(item.strip() for item in file_path.read_text(encoding="utf-8").splitlines() if item.strip())
    )


def _starts_with_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _workflow_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if path.startswith(WORKFLOW_PREFIX)]


def _safe_percentage(risk: str) -> int:
    if risk in {"low", "medium"}:
        return 100
    if risk == "high":
        return 50
    return 0


def _build_decision(risk: str, blocking_reasons: list[str]) -> dict[str, Any]:
    return {
        "color": RISK_COLORS[risk],
        "capacity_parallel_prs": CAPACITY_BY_RISK[risk],
        "safe_percentage": _safe_percentage(risk),
        "next_action": NEXT_ACTION_BY_RISK[risk],
        "requires_human_review": risk in {"high", "blocked"},
        "requires_serialization": risk == "blocked" or bool(blocking_reasons),
    }


def classify_conflict(
    paths: list[str],
    *,
    overlap: bool = False,
    concurrent_hotspots: list[str] | None = None,
) -> dict[str, Any]:
    concurrent_hotspots = sorted(dict.fromkeys(concurrent_hotspots or []))
    current_paths = set(paths)
    concurrent_hotspot_paths = sorted(current_paths.intersection(concurrent_hotspots))
    workflow_paths = _workflow_paths(paths)
    multiple_workflows_changed = len(workflow_paths) > 1

    docs_only = bool(paths) and all(_starts_with_any(path, LOW_RISK_PREFIXES) for path in paths)
    artifact_only = bool(paths) and all(path.startswith("artifacts/") for path in paths)
    runtime_surface_change = any(_starts_with_any(path, HIGH_RISK_PREFIXES) for path in paths)
    medium_surface_change = any(_starts_with_any(path, MEDIUM_RISK_PREFIXES) for path in paths)
    public_contract_change = any(any(hint in path.lower() for hint in CONTRACT_HINTS) for path in paths)

    blocking_reasons: list[str] = []
    risk = "low"

    if overlap:
        blocking_reasons.append("changed_paths_overlap")
    if multiple_workflows_changed:
        blocking_reasons.append("multiple_workflows_changed")
    if concurrent_hotspot_paths:
        blocking_reasons.append("concurrent_hotspots")

    if blocking_reasons:
        risk = "blocked"
    elif runtime_surface_change or public_contract_change:
        risk = "high"
    elif medium_surface_change:
        risk = "medium"

    parallel_safe = risk in {"low", "medium"} and not blocking_reasons
    recommendation = "serializar_merge" if risk == "blocked" else "merge_com_atencao" if risk == "high" else "merge_paralelo_seguro"
    decision = _build_decision(risk, blocking_reasons)

    return {
        "risk": risk,
        "color": decision["color"],
        "lane": "runtime-governance" if docs_only or artifact_only else "implementation",
        "parallel_safe": parallel_safe,
        "capacity_parallel_prs": decision["capacity_parallel_prs"],
        "safe_percentage": decision["safe_percentage"],
        "next_action": decision["next_action"],
        "requires_human_review": decision["requires_human_review"],
        "requires_serialization": decision["requires_serialization"],
        "blocking_reasons": blocking_reasons,
        "changed_paths": paths,
        "critical_files": sorted(
            path
            for path in paths
            if _starts_with_any(path, HIGH_RISK_PREFIXES)
            or any(hint in path.lower() for hint in CONTRACT_HINTS)
            or path in concurrent_hotspot_paths
        ),
        "recommendation": recommendation,
        "signals": {
            "changed_paths_overlap": overlap,
            "multiple_workflows_changed": multiple_workflows_changed,
            "workflow_change_count": len(workflow_paths),
            "workflow_paths": workflow_paths,
            "concurrent_hotspots": bool(concurrent_hotspot_paths),
            "concurrent_hotspot_paths": concurrent_hotspot_paths,
            "public_contract_change": public_contract_change,
            "runtime_surface_change": runtime_surface_change,
            "docs_only": docs_only,
            "artifact_only": artifact_only,
            "medium_surface_change": medium_surface_change,
        },
        "decision": decision,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.2.0",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classifica risco de conflito de PR de forma deterministica.")
    parser.add_argument("paths", nargs="*", help="Paths alterados")
    parser.add_argument("--paths-file", default="", help="Arquivo com um path por linha")
    parser.add_argument("--overlap", action="store_true", help="Sinaliza sobreposicao ja detectada com outro PR")
    parser.add_argument("--hotspots-file", default="", help="Arquivo com paths concorrentes alterados por PRs abertos")
    parser.add_argument("--output", default="artifacts/runtime-governance/conflict-prediction-gate.json")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = load_paths(args.paths, args.paths_file or None)
    concurrent_hotspots = load_optional_paths(args.hotspots_file or None)
    payload = classify_conflict(paths, overlap=args.overlap, concurrent_hotspots=concurrent_hotspots)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            " ".join(
                [
                    f"risk={payload['risk']}",
                    f"color={payload['color']}",
                    f"parallel_safe={payload['parallel_safe']}",
                    f"capacity_parallel_prs={payload['capacity_parallel_prs']}",
                    f"recommendation={payload['recommendation']}",
                ]
            )
        )

    return 1 if payload["risk"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
