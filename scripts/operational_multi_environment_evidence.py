#!/usr/bin/env python3
"""Consolidate current provider-neutral environment probes (report-only)."""

from __future__ import annotations

import argparse
import json
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
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "canonical": canonical,
        "probe_available": probe is not None,
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
    return entry


def consolidate(
    environments_validation: dict[str, Any],
    commit_sha: str,
    correlation_id: str | None = None,
    historical_offline_fly_matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    probes_by_canonical: dict[str, dict[str, Any]] = {}
    for env in environments_validation.get("environments") or []:
        if not isinstance(env, dict):
            continue
        canonical = str(env.get("canonical") or "").strip().lower()
        if not canonical:
            canonical = normalize_env_name(str(env.get("name") or ""))
        probes_by_canonical[canonical] = env

    canonical_keys = sorted(probes_by_canonical)
    environments = [
        build_env_entry(key, probes_by_canonical.get(key))
        for key in canonical_keys
    ]

    ready = sum(1 for item in environments if item.get("status") == "ready")
    degraded = sum(1 for item in environments if item.get("status") == "degraded")
    misaligned = 0

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
            "promotion_order": ["dev", "hml", "prod"],
            "overall_probe_status": summary_probe.get("overall_status"),
        },
        "environments": environments,
        "historical_offline_reference": _historical_offline_reference(historical_offline_fly_matrix),
        "guardrails": [
            "read_only",
            "non_blocking",
            "no_auto_promotion",
            "human_review_required",
        ],
    }


def _historical_offline_reference(matrix: dict[str, Any] | None) -> dict[str, Any] | None:
    if matrix is None:
        return None
    if matrix.get("historical") is not True or matrix.get("offline") is not True:
        raise ValueError("matriz legada só pode ser lida com historical=true e offline=true")
    return {
        "classification": "historical_offline",
        "environments": matrix.get("environments") or {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidate multi-environment operational evidence.")
    parser.add_argument(
        "--environments-validation",
        type=Path,
        default=Path("docs/ops-dashboard/data/environments-validation.json"),
    )
    parser.add_argument("--historical-offline-fly-matrix", type=Path)
    parser.add_argument("--commit-sha", default="local")
    parser.add_argument("--correlation-id", default="")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/operational-multi-environment"))
    args = parser.parse_args()

    env_validation = load_json(args.environments_validation, {"environments": [], "summary": {}})
    legacy_matrix = (
        load_json(args.historical_offline_fly_matrix, {})
        if args.historical_offline_fly_matrix
        else None
    )
    report = consolidate(
        env_validation,
        args.commit_sha,
        args.correlation_id or None,
        legacy_matrix,
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
