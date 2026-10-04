#!/usr/bin/env python3
"""Generate GitLab environments and Review Apps baseline evidence.

Dependency-free baseline for GitLab Edition. It does not deploy anything; it
publishes the intended environment topology and governance rules.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ENVIRONMENTS = [
    {
        "name": "development",
        "type": "persistent",
        "approval": "none",
        "url_variable": "REQSYS_DEV_URL",
        "purpose": "validated integration before staging",
    },
    {
        "name": "staging",
        "type": "persistent",
        "approval": "manual",
        "url_variable": "REQSYS_STAGING_URL",
        "purpose": "pre-production validation and stakeholder review",
    },
    {
        "name": "production",
        "type": "protected",
        "approval": "coordinator_required",
        "url_variable": "REQSYS_PRODUCTION_URL",
        "purpose": "controlled public runtime",
    },
    {
        "name": "review/*",
        "type": "ephemeral",
        "approval": "manual_placeholder",
        "url_variable": "REQSYS_REVIEW_BASE_URL",
        "purpose": "merge request review apps and isolated validation",
    },
]

GOVERNANCE_RULES = [
    "production must be protected and manually approved",
    "review apps must be ephemeral and auto-stopped",
    "environment URLs must come from GitLab variables before real deploy",
    "rollback procedure must be documented before production activation",
    "deploy jobs must publish evidence artifacts when real deploy is enabled",
]


def build_report() -> dict[str, object]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": os.getenv("CI_COMMIT_SHA", "local"),
        "branch": os.getenv("CI_COMMIT_REF_NAME", "local"),
        "pipeline_source": os.getenv("CI_PIPELINE_SOURCE", "local"),
        "status": "baseline_defined",
        "environments": ENVIRONMENTS,
        "governance_rules": GOVERNANCE_RULES,
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# GitLab Environments Baseline Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Commit: {report['commit']}",
        f"Branch: {report['branch']}",
        f"Status: {report['status']}",
        "",
        "## Environments",
        "",
        "| Environment | Type | Approval | URL variable |",
        "|---|---|---|---|",
    ]
    for item in report["environments"]:  # type: ignore[index]
        lines.append(
            f"| {item['name']} | {item['type']} | {item['approval']} | `{item['url_variable']}` |"
        )
    lines.extend(["", "## Governance rules", ""])
    for rule in report["governance_rules"]:  # type: ignore[index]
        lines.append(f"- {rule}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="-")
    parser.add_argument("--markdown", default=None)
    args = parser.parse_args()

    report = build_report()
    json_content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"

    if args.output == "-":
        print(json_content, end="")
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_content, encoding="utf-8")

    if args.markdown:
        markdown_path = Path(args.markdown)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
