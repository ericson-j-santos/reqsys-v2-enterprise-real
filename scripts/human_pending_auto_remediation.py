#!/usr/bin/env python3
"""Executa remediações automáticas antes de escalar uma pendência humana.

A rotina é deliberadamente pequena: ela só dispara workflows explicitamente
allowlisted e nunca tenta fabricar segredo, aprovação, identidade externa ou
evidência. Falha recente permanece visível para o Human Pending Satellite.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RemediationPolicy:
    issue_number: int
    workflow: str
    cooldown_minutes: int
    inputs: dict[str, Any]
    suppress_human_on_success: bool = True


POLICIES = (
    RemediationPolicy(
        issue_number=1130,
        workflow="github-workflow-permission-readiness-watch.yml",
        cooldown_minutes=70,
        inputs={"enforce": False},
    ),
    RemediationPolicy(
        issue_number=1520,
        workflow="movimento-email-dsn-bootstrap.yml",
        cooldown_minutes=240,
        inputs={},
    ),
    RemediationPolicy(
        issue_number=1532,
        workflow="teams-bot-dev-provision.yml",
        cooldown_minutes=70,
        inputs={"force_runtime_sync": False},
        # Um provisionamento verde ainda exige a primeira interação do usuário
        # no Teams para materializar conversationReference.
        suppress_human_on_success=False,
    ),
)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def decide(
    policy: RemediationPolicy,
    *,
    issue_open: bool,
    runs: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    base = {
        "issue_number": policy.issue_number,
        "workflow": policy.workflow,
        "suppress_human": False,
        "dispatch_required": False,
    }
    if not issue_open:
        return base | {"state": "issue_closed", "reason": "issue_closed"}

    latest = runs[0] if runs else None
    if latest and latest.get("status") in {"queued", "in_progress", "requested", "waiting", "pending"}:
        return base | {
            "state": "in_progress",
            "reason": "automatic_remediation_running",
            "suppress_human": True,
            "run_url": latest.get("html_url"),
        }

    if latest:
        observed = parse_timestamp(latest.get("updated_at") or latest.get("created_at"))
        if observed is not None and now - observed <= timedelta(minutes=policy.cooldown_minutes):
            conclusion = str(latest.get("conclusion") or "").lower()
            if conclusion == "success":
                return base | {
                    "state": "recent_success",
                    "reason": "automatic_remediation_recently_succeeded",
                    "suppress_human": policy.suppress_human_on_success,
                    "run_url": latest.get("html_url"),
                }
            return base | {
                "state": "blocked",
                "reason": f"automatic_remediation_{conclusion or 'unknown'}",
                "run_url": latest.get("html_url"),
            }

    return base | {
        "state": "dispatch_required",
        "reason": "no_recent_automatic_remediation",
        "dispatch_required": True,
    }


class GitHub:
    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo
        self.base = "https://api.github.com"

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base + path,
            method=method,
            data=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "reqsys-human-pending-auto-remediation",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    def issue_open(self, number: int) -> bool:
        issue = self.request("GET", f"/repos/{self.repo}/issues/{number}")
        return issue.get("state") == "open"

    def workflow_runs(self, workflow: str) -> list[dict[str, Any]]:
        encoded = urllib.parse.quote(workflow, safe="")
        payload = self.request(
            "GET",
            f"/repos/{self.repo}/actions/workflows/{encoded}/runs?branch=main&per_page=10",
        )
        return [
            run
            for run in payload.get("workflow_runs", [])
            if run.get("event") in {"workflow_dispatch", "schedule", "push"}
        ]

    def dispatch(self, policy: RemediationPolicy) -> None:
        encoded = urllib.parse.quote(policy.workflow, safe="")
        self.request(
            "POST",
            f"/repos/{self.repo}/actions/workflows/{encoded}/dispatches",
            {"ref": "main", "inputs": policy.inputs},
        )


def run(token: str, repo: str, output: Path, now: datetime | None = None) -> int:
    gh = GitHub(token, repo)
    current = now or datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []

    for policy in POLICIES:
        try:
            decision = decide(
                policy,
                issue_open=gh.issue_open(policy.issue_number),
                runs=gh.workflow_runs(policy.workflow),
                now=current,
            )
            if decision["dispatch_required"]:
                gh.dispatch(policy)
                decision = decision | {
                    "state": "dispatched",
                    "reason": "automatic_remediation_dispatched",
                    "dispatch_required": False,
                    "suppress_human": True,
                }
        except Exception as exc:  # fail-closed: satellite continues and may escalate
            decision = {
                "issue_number": policy.issue_number,
                "workflow": policy.workflow,
                "state": "error",
                "reason": exc.__class__.__name__,
                "dispatch_required": False,
                "suppress_human": False,
            }
        results.append(decision)

    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": current.isoformat(),
        "repository": repo,
        "policies": [asdict(item) for item in POLICIES],
        "results": results,
        "secret_value_exposed": False,
        "production_touched": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"remediations": len(results), "states": {str(item["issue_number"]): item["state"] for item in results}}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/human-pending-satellite/remediation.json"),
    )
    args = parser.parse_args()
    if not args.repo or not args.token:
        raise SystemExit("repo/token required")
    return run(args.token, args.repo, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
