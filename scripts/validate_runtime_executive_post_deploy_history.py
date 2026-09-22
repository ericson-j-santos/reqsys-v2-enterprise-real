#!/usr/bin/env python3
"""Validate Runtime Executive post-deploy history contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "docs" / "ops-dashboard" / "data" / "runtime-executive-post-deploy-history.json"
BRIEF = ROOT / "docs" / "ops-dashboard" / "data" / "executive-brief.json"

REQUIRED_SUMMARY = {
    "samples",
    "availability_percent",
    "avg_latency_ms",
    "max_latency_ms",
    "failure_count",
    "score_trend",
    "latency_trend",
    "failure_trend",
    "stability",
}


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"arquivo ausente: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    history = load(HISTORY)
    if history.get("contract") != "runtime-executive-post-deploy-history":
        raise SystemExit("contract invalido no historico post-deploy")
    summary = history.get("summary") or {}
    missing = sorted(REQUIRED_SUMMARY - set(summary))
    if missing:
        raise SystemExit(f"summary sem campos obrigatorios: {missing}")
    samples = history.get("history") or []
    if len(samples) > int(history.get("limit") or 200):
        raise SystemExit("historico excedeu limite configurado")
    for index, sample in enumerate(samples):
        for field in ("timestamp", "validated_at_epoch", "state", "availability_percent", "executive_score", "failure_count"):
            if field not in sample:
                raise SystemExit(f"sample {index} sem campo {field}")
    brief = load(BRIEF)
    estado = brief.get("estado_unico") or {}
    if "runtime_executive_post_deploy_history" not in estado:
        raise SystemExit("executive brief sem runtime_executive_post_deploy_history")
    links = brief.get("links") or {}
    if links.get("runtime_executive_post_deploy_history") != "docs/ops-dashboard/data/runtime-executive-post-deploy-history.json":
        raise SystemExit("executive brief sem link oficial do historico")
    print("runtime executive post-deploy history validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
