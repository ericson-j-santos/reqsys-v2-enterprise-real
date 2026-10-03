#!/usr/bin/env python3
"""Normalize CI and runtime completion evidence; legacy Fly evidence is offline-only."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SUCCESS = "succeeded"
CI_WORKFLOWS = {
    "CI — ReqSys v2 Enterprise",
    "CI ReqSys v2 Enterprise",
    "CI Enterprise Fast",
    "CI Enterprise Regression",
    "Fast CI - Operational Guardrails",
    "Governance Quality Gates",
    "Governança Padrão Ouro",
}


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def event(environment: str, stage: str, run: dict[str, Any], *, evidence_url: str | None = None) -> dict[str, Any]:
    conclusion = str(run.get("conclusion") or "").lower()
    status = SUCCESS if conclusion == "success" else ("failed" if conclusion in {"failure", "timed_out"} else "in_progress")
    return {
        "environment": environment,
        "stage": stage,
        "status": status,
        "commit_sha": run.get("head_sha"),
        "evidence_url": evidence_url or run.get("html_url"),
        "updated_at": run.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        "source": "github-actions",
        "source_run_id": run.get("id"),
    }


def artifact_environment(name: str) -> str | None:
    prefix = "fly-homologation-"
    if not name.startswith(prefix):
        return None
    candidate = name[len(prefix):].lower()
    return candidate if candidate in {"dev", "stg", "prod"} else None


def _is_retired_fly_url(value: str | None) -> bool:
    hostname = (urlparse(str(value or "")).hostname or "").lower().rstrip(".")
    return hostname in {"fly.dev", "fly.io"} or hostname.endswith((".fly.dev", ".fly.io"))


def normalize(
    runs_payload: dict[str, Any],
    artifacts_payload: dict[str, Any],
    health_payload: dict[str, Any],
    *,
    include_historical_offline: bool = False,
) -> list[dict[str, Any]]:
    legacy_marked = all(
        payload.get("historical") is True and payload.get("offline") is True
        for payload in (runs_payload, artifacts_payload)
    )
    include_legacy = include_historical_offline and legacy_marked
    runs = runs_payload.get("workflow_runs") or []
    artifacts_by_run: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in artifacts_payload.get("artifacts") or []:
        run_id = int(item.get("workflow_run_id") or 0)
        artifacts_by_run[run_id].append(item)

    executions: dict[str, dict[str, Any]] = {}
    for run in runs:
        sha = str(run.get("head_sha") or "").strip()
        if not sha:
            continue
        execution = executions.setdefault(
            sha,
            {"execution_id": f"delivery-{sha}", "item_id": f"commit-{sha[:12]}", "expected_commit_sha": sha, "events": []},
        )
        if run.get("name") in CI_WORKFLOWS:
            execution["events"].append(event("dev", "build", run))

        for artifact in artifacts_by_run.get(int(run.get("id") or 0), []):
            if not include_legacy or run.get("historical") is not True or run.get("offline") is not True:
                continue
            environment = artifact_environment(str(artifact.get("name") or ""))
            if not environment:
                continue
            url = artifact.get("archive_download_url") or run.get("html_url")
            if environment == "dev":
                stages = ("deploy", "smoke-test")
            elif environment == "stg":
                stages = ("deploy", "integration-test", "homologation")
            else:
                stages = ("deploy",)
            for stage in stages:
                legacy_event = event(environment, stage, run, evidence_url=url)
                legacy_event.update(
                    {"historical": True, "offline": True, "classification": "historical_offline"}
                )
                execution["events"].append(legacy_event)

    legacy_health = _is_retired_fly_url(health_payload.get("evidence_url"))
    if legacy_health and not (
        include_historical_offline
        and health_payload.get("historical") is True
        and health_payload.get("offline") is True
    ):
        health_payload = {}
    prod_sha = str(health_payload.get("commit_sha") or "").strip()
    checks = health_payload.get("checks") or []
    if prod_sha and checks:
        execution = executions.setdefault(
            prod_sha,
            {"execution_id": f"delivery-{prod_sha}", "item_id": f"commit-{prod_sha[:12]}", "expected_commit_sha": prod_sha, "events": []},
        )
        all_healthy = all(check.get("healthy") is True for check in checks)
        runtime_run = {
            "id": health_payload.get("run_id"),
            "head_sha": prod_sha,
            "conclusion": "success" if all_healthy else "failure",
            "html_url": health_payload.get("evidence_url"),
            "updated_at": health_payload.get("observed_at"),
        }
        health_event = event("prod", "runtime-health", runtime_run)
        validation_event = event("prod", "post-deploy-validation", runtime_run)
        if legacy_health:
            for item in (health_event, validation_event):
                item.update(
                    {"historical": True, "offline": True, "classification": "historical_offline"}
                )
        execution["events"].append(health_event)
        execution["events"].append(validation_event)

    return sorted(executions.values(), key=lambda item: item["execution_id"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--health", required=True, type=Path)
    parser.add_argument("--include-historical-offline-fly-evidence", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = normalize(
        load_json(args.runs),
        load_json(args.artifacts),
        load_json(args.health),
        include_historical_offline=args.include_historical_offline_fly_evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"executions": len(result)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
