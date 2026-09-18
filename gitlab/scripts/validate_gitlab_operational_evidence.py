#!/usr/bin/env python3
"""Validate operational GitLab evidence required for ReqSys Gold Standard.

The gate checks the current pipeline, security scanners, protected default branch,
merge approvals and successful deployment evidence. It uses only Python's
standard library and can run against the GitLab API or a deterministic fixture.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_SCANNER_JOBS = {
    "backend_sast_bandit",
    "secret_detection_gitleaks",
    "backend_dependency_scanning_pip_audit",
    "frontend_dependency_scanning_npm_audit",
    "container_scanning_trivy",
}
SUCCESS_STATUSES = {"success", "passed"}
ACTIVE_STATUSES = SUCCESS_STATUSES | {"running"}


class GateConfigurationError(RuntimeError):
    """Raised when mandatory execution configuration is absent or invalid."""


@dataclass(frozen=True)
class GateConfig:
    api_url: str
    project_id: str
    pipeline_id: str
    default_branch: str
    token: str
    environment: str
    timeout_seconds: int = 20

    @classmethod
    def from_environment(cls) -> "GateConfig":
        values = {
            "api_url": os.getenv("CI_API_V4_URL", "").rstrip("/"),
            "project_id": os.getenv("CI_PROJECT_ID", ""),
            "pipeline_id": os.getenv("CI_PIPELINE_ID", ""),
            "default_branch": os.getenv("CI_DEFAULT_BRANCH", "main"),
            "token": os.getenv("GITLAB_GOVERNANCE_TOKEN", ""),
            "environment": os.getenv("GITLAB_EVIDENCE_ENVIRONMENT", "staging"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise GateConfigurationError(
                "Missing mandatory configuration: " + ", ".join(sorted(missing))
            )
        timeout_raw = os.getenv("GITLAB_API_TIMEOUT_SECONDS", "20")
        try:
            timeout_seconds = int(timeout_raw)
        except ValueError as exc:
            raise GateConfigurationError(
                "GITLAB_API_TIMEOUT_SECONDS must be an integer"
            ) from exc
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise GateConfigurationError(
                "GITLAB_API_TIMEOUT_SECONDS must be between 1 and 120"
            )
        return cls(timeout_seconds=timeout_seconds, **values)


class GitLabApiClient:
    def __init__(self, config: GateConfig) -> None:
        self.config = config

    def get(self, path: str, query: dict[str, str] | None = None) -> Any:
        encoded_project = urllib.parse.quote(self.config.project_id, safe="")
        normalized_path = path.format(project_id=encoded_project).lstrip("/")
        url = f"{self.config.api_url}/{normalized_path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(
            url,
            headers={
                "PRIVATE-TOKEN": self.config.token,
                "Accept": "application/json",
                "User-Agent": "reqsys-gitlab-operational-evidence-gate/1.0",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.timeout_seconds
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitLab API returned HTTP {exc.code} for {url}: {body[:500]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitLab API unavailable for {url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"GitLab API returned invalid JSON for {url}") from exc


def collect_api_evidence(config: GateConfig) -> dict[str, Any]:
    client = GitLabApiClient(config)
    project_path = "projects/{project_id}"
    pipeline_path = f"{project_path}/pipelines/{config.pipeline_id}"
    branch_encoded = urllib.parse.quote(config.default_branch, safe="")

    project = client.get(project_path)
    pipeline = client.get(pipeline_path)
    jobs = client.get(f"{pipeline_path}/jobs", {"per_page": "100"})
    protected_branch = client.get(
        f"{project_path}/protected_branches/{branch_encoded}"
    )

    approval_rules: Any
    try:
        approval_rules = client.get(f"{project_path}/approval_rules")
    except RuntimeError:
        approval_rules = []

    deployments = client.get(
        f"{project_path}/deployments",
        {
            "environment": config.environment,
            "status": "success",
            "order_by": "updated_at",
            "sort": "desc",
            "per_page": "20",
        },
    )

    return {
        "project": project,
        "pipeline": pipeline,
        "jobs": jobs,
        "protected_branch": protected_branch,
        "approval_rules": approval_rules,
        "deployments": deployments,
        "environment": config.environment,
    }


def _approval_count(evidence: dict[str, Any]) -> int:
    rules = evidence.get("approval_rules") or []
    if isinstance(rules, dict):
        rules = rules.get("rules", [])
    counts = [
        int(rule.get("approvals_required", 0))
        for rule in rules
        if isinstance(rule, dict)
    ]
    if counts:
        return max(counts)
    project = evidence.get("project") or {}
    return int(project.get("approvals_before_merge", 0) or 0)


def evaluate(evidence: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    pipeline = evidence.get("pipeline") or {}
    pipeline_status = str(pipeline.get("status", "missing")).lower()
    pipeline_real = bool(pipeline.get("id")) and pipeline_status in ACTIVE_STATUSES
    add(
        "pipeline_real",
        pipeline_real,
        f"pipeline_id={pipeline.get('id', 'missing')}; status={pipeline_status}",
    )

    jobs = evidence.get("jobs") or []
    scanner_status = {
        str(job.get("name")): str(job.get("status", "missing")).lower()
        for job in jobs
        if isinstance(job, dict) and job.get("name") in REQUIRED_SCANNER_JOBS
    }
    missing_scanners = sorted(REQUIRED_SCANNER_JOBS - set(scanner_status))
    failed_scanners = sorted(
        name for name, status in scanner_status.items() if status not in SUCCESS_STATUSES
    )
    scanners_ok = not missing_scanners and not failed_scanners
    add(
        "security_scanners",
        scanners_ok,
        f"missing={missing_scanners or 'none'}; non_success={failed_scanners or 'none'}",
    )

    protected = evidence.get("protected_branch") or {}
    push_levels = protected.get("push_access_levels") or []
    merge_levels = protected.get("merge_access_levels") or []
    branch_protected = bool(protected.get("name")) and bool(merge_levels) and bool(
        push_levels
    )
    add(
        "default_branch_protection",
        branch_protected,
        f"branch={protected.get('name', 'missing')}; push_rules={len(push_levels)}; merge_rules={len(merge_levels)}",
    )

    approvals_required = _approval_count(evidence)
    add(
        "merge_approvals",
        approvals_required >= 1,
        f"approvals_required={approvals_required}",
    )

    environment = str(evidence.get("environment", "staging"))
    deployments = evidence.get("deployments") or []
    successful_deployments = [
        item
        for item in deployments
        if isinstance(item, dict)
        and str(item.get("status", "")).lower() in SUCCESS_STATUSES
    ]
    add(
        "deployment_evidence",
        bool(successful_deployments),
        f"environment={environment}; successful_deployments={len(successful_deployments)}",
    )

    return all(check["passed"] for check in checks), checks


def build_report(ok: bool, checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if ok else "failed",
        "gate": "gitlab_operational_evidence",
        "checks": checks,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# GitLab Operational Evidence Gate",
        "",
        f"Generated at: {report['generated_at']}",
        f"Status: **{report['status']}**",
        "",
        "| Check | Status | Evidence |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        detail = str(check["detail"]).replace("|", "\\|")
        lines.append(f"| `{check['name']}` | {status} | {detail} |")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gitlab-operational-evidence.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "gitlab-operational-evidence.md").write_text(
        render_markdown(report), encoding="utf-8"
    )


def load_fixture(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GateConfigurationError(f"Fixture not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GateConfigurationError(f"Invalid fixture JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise GateConfigurationError("Fixture root must be a JSON object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("audit"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        evidence = (
            load_fixture(args.fixture)
            if args.fixture
            else collect_api_evidence(GateConfig.from_environment())
        )
        ok, checks = evaluate(evidence)
        report = build_report(ok, checks)
        write_outputs(report, args.output_dir)
        print(render_markdown(report))
        return 0 if ok else 1
    except (GateConfigurationError, RuntimeError) as exc:
        report = build_report(
            False,
            [{"name": "gate_execution", "passed": False, "detail": str(exc)}],
        )
        write_outputs(report, args.output_dir)
        print(render_markdown(report), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
