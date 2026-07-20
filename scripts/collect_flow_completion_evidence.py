#!/usr/bin/env python3
"""Normaliza evidências reais de CI, homologação Fly e runtime no contrato do Flow Completion Monitor."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUCCESS = "succeeded"
CI_WORKFLOWS = {
    "CI — ReqSys v2 Enterprise",
    "Fast CI - Operational Guardrails",
    "Governança Padrão Ouro",
    "Governance Quality Gates",
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


def normalize(runs_payload: dict[str, Any], artifacts_payload: dict[str, Any], health_payload: dict[str, Any]) -> list[dict[str, Any]]:
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
                execution["events"].append(event(environment, stage, run, evidence_url=url))

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
        execution["events"].append(event("prod", "runtime-health", runtime_run))
        execution["events"].append(event("prod", "post-deploy-validation", runtime_run))

    return sorted(executions.values(), key=lambda item: item["execution_id"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--health", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = normalize(load_json(args.runs), load_json(args.artifacts), load_json(args.health))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"executions": len(result)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
