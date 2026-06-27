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


def load_paths(raw_paths: list[str], paths_file: str | None = None) -> list[str]:
    paths = [item.strip() for item in raw_paths if item.strip()]
    if paths_file:
        file_path = Path(paths_file)
        if file_path.exists():
            paths.extend(item.strip() for item in file_path.read_text(encoding="utf-8").splitlines() if item.strip())
    return sorted(dict.fromkeys(paths))


def _starts_with_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def classify_conflict(paths: list[str], *, overlap: bool = False) -> dict[str, Any]:
    docs_only = bool(paths) and all(_starts_with_any(path, LOW_RISK_PREFIXES) for path in paths)
    artifact_only = bool(paths) and all(path.startswith("artifacts/") for path in paths)
    runtime_surface_change = any(_starts_with_any(path, HIGH_RISK_PREFIXES) for path in paths)
    medium_surface_change = any(_starts_with_any(path, MEDIUM_RISK_PREFIXES) for path in paths)
    public_contract_change = any(any(hint in path.lower() for hint in CONTRACT_HINTS) for path in paths)

    blocking_reasons: list[str] = []
    risk = "low"

    if overlap:
        risk = "blocked"
        blocking_reasons.append("changed_paths_overlap")
    elif runtime_surface_change or public_contract_change:
        risk = "high"
    elif medium_surface_change:
        risk = "medium"

    parallel_safe = risk in {"low", "medium"} and not blocking_reasons

    return {
        "risk": risk,
        "lane": "runtime-governance" if docs_only or artifact_only else "implementation",
        "parallel_safe": parallel_safe,
        "blocking_reasons": blocking_reasons,
        "changed_paths": paths,
        "signals": {
            "changed_paths_overlap": overlap,
            "public_contract_change": public_contract_change,
            "runtime_surface_change": runtime_surface_change,
            "docs_only": docs_only,
            "artifact_only": artifact_only,
            "medium_surface_change": medium_surface_change,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0.0",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classifica risco de conflito de PR de forma deterministica.")
    parser.add_argument("paths", nargs="*", help="Paths alterados")
    parser.add_argument("--paths-file", default="", help="Arquivo com um path por linha")
    parser.add_argument("--overlap", action="store_true", help="Sinaliza sobreposicao ja detectada com outro PR")
    parser.add_argument("--output", default="artifacts/runtime-governance/conflict-prediction-gate.json")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = load_paths(args.paths, args.paths_file or None)
    payload = classify_conflict(paths, overlap=args.overlap)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"risk={payload['risk']} parallel_safe={payload['parallel_safe']}")

    return 1 if payload["risk"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
