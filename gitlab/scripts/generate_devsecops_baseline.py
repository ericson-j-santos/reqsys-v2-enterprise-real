#!/usr/bin/env python3
"""Generate GitLab DevSecOps baseline evidence for ReqSys.

This report is dependency-free and intentionally conservative. It documents
which GitLab-native security capabilities should be enabled when the project
is imported into GitLab with runners and licensed features.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

CAPABILITIES = [
    {
        "name": "sast",
        "status": "placeholder_ready",
        "target": "Enable GitLab SAST template or equivalent scanner",
        "artifact": "gl-sast-report.json",
    },
    {
        "name": "secret_detection",
        "status": "placeholder_ready",
        "target": "Enable GitLab Secret Detection and block exposed secrets",
        "artifact": "gl-secret-detection-report.json",
    },
    {
        "name": "dependency_scanning",
        "status": "placeholder_ready",
        "target": "Enable dependency scanning for backend/frontend packages",
        "artifact": "gl-dependency-scanning-report.json",
    },
    {
        "name": "container_scanning",
        "status": "placeholder_ready",
        "target": "Enable image scanning when container registry is configured",
        "artifact": "gl-container-scanning-report.json",
    },
    {
        "name": "sbom",
        "status": "placeholder_ready",
        "target": "Publish CycloneDX SBOM artifacts when dependency graph is available",
        "artifact": "gl-sbom-report.cdx.json",
    },
]


def build_report() -> dict[str, object]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": os.getenv("CI_COMMIT_SHA", "local"),
        "branch": os.getenv("CI_COMMIT_REF_NAME", "local"),
        "pipeline_source": os.getenv("CI_PIPELINE_SOURCE", "local"),
        "status": "baseline_defined",
        "capabilities": CAPABILITIES,
        "merge_policy": [
            "block merge on critical/high vulnerabilities after real scanners are enabled",
            "block merge on exposed secrets",
            "publish evidence artifacts for every security stage",
            "require coordinator review for security exceptions",
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# GitLab DevSecOps Baseline Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"Commit: {report['commit']}",
        f"Branch: {report['branch']}",
        f"Status: {report['status']}",
        "",
        "## Capabilities",
        "",
        "| Capability | Status | Target artifact |",
        "|---|---|---|",
    ]
    for item in report["capabilities"]:  # type: ignore[index]
        lines.append(f"| {item['name']} | {item['status']} | `{item['artifact']}` |")
    lines.extend(["", "## Merge policy", ""])
    for policy in report["merge_policy"]:  # type: ignore[index]
        lines.append(f"- {policy}")
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
