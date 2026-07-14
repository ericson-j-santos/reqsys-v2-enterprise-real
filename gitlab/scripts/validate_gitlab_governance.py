#!/usr/bin/env python3
"""GitLab Edition governance validator for ReqSys.

Dependency-free validation focused on critical structure only.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FILES = [
    ".gitlab-ci.yml",
    ".gitlab/issue_templates/reqsys_task.md",
    ".gitlab/merge_request_templates/default.md",
    "gitlab/docs/GITLAB_OPERATING_MODEL.md",
    "gitlab/docs/GITLAB_DEVSECOPS_BASELINE.md",
    "gitlab/docs/GITLAB_ENVIRONMENTS_REVIEW_APPS.md",
    "gitlab/ci/classify.yml",
    "gitlab/ci/governance.yml",
    "gitlab/ci/runtime.yml",
    "gitlab/ci/security.yml",
    "gitlab/ci/devsecops.yml",
    "gitlab/ci/environments.yml",
    "gitlab/ci/evidence.yml",
    "gitlab/ci/deploy.yml",
    "gitlab/scripts/classify_issue.py",
    "gitlab/scripts/generate_semantic_pipeline_report.py",
    "gitlab/scripts/generate_devsecops_baseline.py",
    "gitlab/scripts/generate_environments_baseline.py",
    "gitlab/scripts/validate_gitlab_governance.py",
    "gitlab/scripts/validate_gitlab_operational_evidence.py",
    "gitlab/tests/test_validate_gitlab_operational_evidence.py",
]

REQUIRED_CI_TERMS = [
    "stages:",
    "workflow:",
    "include:",
    "gitlab/ci/classify.yml",
    "gitlab/ci/governance.yml",
    "gitlab/ci/runtime.yml",
    "gitlab/ci/security.yml",
    "gitlab/ci/devsecops.yml",
    "gitlab/ci/environments.yml",
    "gitlab/ci/evidence.yml",
    "gitlab/ci/deploy.yml",
]

REQUIRED_INCLUDE_TERMS = {
    "gitlab/ci/classify.yml": ["classify_changes", "semantic_pipeline_routing", "artifacts:"],
    "gitlab/ci/governance.yml": ["gitlab_governance_validation", "artifacts:"],
    "gitlab/ci/runtime.yml": ["runtime_backend_smoke", "pytest", "rules:", "changes:"],
    "gitlab/ci/security.yml": ["security_baseline_smoke", "backend_sast_bandit", "artifacts:"],
    "gitlab/ci/devsecops.yml": [
        "gitlab_devsecops_baseline",
        "secret_detection_gitleaks",
        "backend_dependency_scanning_pip_audit",
        "frontend_dependency_scanning_npm_audit",
        "container_scanning_trivy",
        "artifacts:",
    ],
    "gitlab/ci/environments.yml": ["gitlab_environments_baseline", "review_app_placeholder", "stop_review_app_placeholder", "environment:"],
    "gitlab/ci/evidence.yml": [
        "gitlab_evidence_summary",
        "gitlab_operational_evidence_gate",
        "GITLAB_GOVERNANCE_TOKEN",
        "validate_gitlab_operational_evidence.py",
        "gitlab-operational-evidence.json",
        "artifacts:",
    ],
    "gitlab/ci/deploy.yml": ["deploy_staging_fly", "FLY_API_TOKEN", "environment:"],
}

FORBIDDEN_CI_TERMS = [
    "write-all",
    "CI_JOB_TOKEN=",
    "PRIVATE_TOKEN=",
    "password=",
    "secret=",
]


def validate() -> tuple[bool, list[str]]:
    issues: list[str] = []

    for file_path in REQUIRED_FILES:
        if not Path(file_path).exists():
            issues.append(f"MISSING_FILE: {file_path}")

    ci_path = Path(".gitlab-ci.yml")
    if ci_path.exists():
        ci_text = ci_path.read_text(encoding="utf-8")
        for term in REQUIRED_CI_TERMS:
            if term not in ci_text:
                issues.append(f"MISSING_CI_TERM: {term}")
        lowered = ci_text.lower()
        for term in FORBIDDEN_CI_TERMS:
            if term.lower() in lowered:
                issues.append(f"FORBIDDEN_CI_TERM: {term}")

    for include_path, required_terms in REQUIRED_INCLUDE_TERMS.items():
        path = Path(include_path)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for term in required_terms:
            if term not in text:
                issues.append(f"MISSING_INCLUDE_TERM: {include_path}: {term}")

    return not issues, issues


def render_report(ok: bool, issues: list[str]) -> str:
    status = "passed" if ok else "failed"
    lines = [
        "# GitLab Governance Report",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"Status: {status}",
        "",
        "## Required files",
    ]
    lines.extend(f"- `{file_path}`" for file_path in REQUIRED_FILES)
    lines.extend(["", "## Issues"])
    if issues:
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    ok, issues = validate()
    report = render_report(ok, issues)

    if args.output == "-":
        print(report)
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
