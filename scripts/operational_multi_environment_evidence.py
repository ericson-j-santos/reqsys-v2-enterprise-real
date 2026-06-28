#!/usr/bin/env python3
"""Consolidate multi-environment operational evidence (report-only).

Merges environment readiness probes with Fly canonical matrix into a single
artifact for dashboards, coordenador and drift analysis.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ENV_ALIAS = {
    "desenvolvimento": "dev",
    "dev": "dev",
    "testes": "test",
    "test": "test",
    "homologacao": "hml",
    "hml": "hml",
    "staging": "hml",
    "producao": "prod",
    "prod": "prod",
    "production": "prod",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_env_name(name: str) -> str:
    return ENV_ALIAS.get(name.strip().lower(), name.strip().lower())


def build_env_entry(
    canonical: str,
    probe: dict[str, Any] | None,
    fly_env: dict[str, Any] | None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "canonical": canonical,
        "probe_available": probe is not None,
        "fly_matrix_available": fly_env is not None,
    }
    if probe:
        entry.update(
            {
                "probe_name": probe.get("name"),
                "status": probe.get("status"),
                "readiness_percent": probe.get("readiness_percent"),
                "operational_risk": probe.get("operational_risk"),
                "frontend_url": probe.get("frontend"),
                "api_url": probe.get("api"),
            }
        )
    if fly_env:
        entry.update(
            {
                "fly_api_url": fly_env.get("api_url"),
                "fly_frontend_url": fly_env.get("frontend_url"),
                "app_env": fly_env.get("app_env"),
                "smoke_endpoints": fly_env.get("smoke_endpoints", []),
            }
        )
    if probe and fly_env:
        api_match = (probe.get("api") or "").rstrip("/") == (fly_env.get("api_url") or "").rstrip("/")
        frontend_match = (probe.get("frontend") or "").rstrip("/") == (
            fly_env.get("frontend_url") or ""
        ).rstrip("/")
        entry["url_matrix_aligned"] = api_match and frontend_match
    else:
        entry["url_matrix_aligned"] = None
    return entry


def consolidate(
    environments_validation: dict[str, Any],
    fly_matrix: dict[str, Any],
    commit_sha: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    probes_by_canonical: dict[str, dict[str, Any]] = {}
    for env in environments_validation.get("environments") or []:
        if not isinstance(env, dict):
            continue
        canonical = normalize_env_name(str(env.get("name") or ""))
        probes_by_canonical[canonical] = env

    fly_envs = (fly_matrix.get("environments") or {}) if isinstance(fly_matrix, dict) else {}
    canonical_keys = sorted(set(probes_by_canonical) | set(fly_envs))
    environments = [
        build_env_entry(key, probes_by_canonical.get(key), fly_envs.get(key))
        for key in canonical_keys
    ]

    ready = sum(1 for item in environments if item.get("status") == "ready")
    degraded = sum(1 for item in environments if item.get("status") == "degraded")
    misaligned = sum(1 for item in environments if item.get("url_matrix_aligned") is False)

    if misaligned > 0 or degraded > 0:
        status = "degraded"
        operational_risk = "medium" if misaligned == 0 else "high"
    elif ready == len([e for e in environments if e.get("probe_available")]):
        status = "ready"
        operational_risk = "low"
    else:
        status = "partial"
        operational_risk = "medium"

    summary_probe = environments_validation.get("summary") or {}
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "operational-multi-environment-evidence",
        "status": status,
        "confidence_level": "high" if probes_by_canonical else "low",
        "maturity_percent": round(
            float(summary_probe.get("average_readiness_percent") or 0) if summary_probe else 50.0,
            2,
        ),
        "operational_risk": operational_risk,
        "commit_sha": commit_sha,
        "correlation_id": correlation_id or str(uuid4()),
        "mode": "report_only",
        "summary": {
            "environments_total": len(environments),
            "ready": ready,
            "degraded": degraded,
            "url_matrix_misaligned": misaligned,
            "promotion_order": fly_matrix.get("promotion_order") or ["dev", "hml", "prod"],
            "overall_probe_status": summary_probe.get("overall_status"),
        },
        "environments": environments,
        "guardrails": [
            "read_only",
            "non_blocking",
            "no_auto_promotion",
            "human_review_required",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidate multi-environment operational evidence.")
    parser.add_argument(
        "--environments-validation",
        type=Path,
        default=Path("docs/ops-dashboard/data/environments-validation.json"),
    )
    parser.add_argument("--fly-matrix", type=Path, default=Path("infra/fly-environments.json"))
    parser.add_argument("--commit-sha", default="local")
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-multi-environment"))
    args = parser.parse_args()

    env_validation = load_json(args.environments_validation, {"environments": [], "summary": {}})
    fly_matrix = load_json(args.fly_matrix, {"environments": {}})
    report = consolidate(
        env_validation,
        fly_matrix,
        args.commit_sha,
        args.correlation_id or None,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "multi-environment-evidence.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
