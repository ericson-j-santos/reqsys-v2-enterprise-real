#!/usr/bin/env python3
"""Generate GitLab semantic pipeline routing evidence.

Dependency-free and safe for CI. It documents which domain pipelines are
available and which path groups activate them.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROUTES = [
    {
        "domain": "runtime",
        "label": "ia:runtime",
        "include": "gitlab/ci/runtime.yml",
        "paths": ["backend/**/*", "runtime/**/*", "infra/**/*"],
    },
    {
        "domain": "observability",
        "label": "ia:observability",
        "include": "gitlab/ci/evidence.yml",
        "paths": ["observability/**/*", "audit/**/*", "gitlab/**/*"],
    },
    {
        "domain": "governance-ci",
        "label": "ia:governance-ci",
        "include": "gitlab/ci/governance.yml",
        "paths": [".gitlab-ci.yml", "gitlab/ci/**/*", "gitlab/scripts/**/*"],
    },
    {
        "domain": "security",
        "label": "ia:governance-ci",
        "include": "gitlab/ci/security.yml",
        "paths": ["security/**/*", "gitlab/**/*", ".gitlab-ci.yml"],
    },
    {
        "domain": "deploy",
        "label": "ia:runtime",
        "include": "gitlab/ci/deploy.yml",
        "paths": ["infra/**/*", "deploy/**/*", ".gitlab-ci.yml"],
    },
]


def build_report() -> dict[str, object]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": os.getenv("CI_COMMIT_SHA", "local"),
        "branch": os.getenv("CI_COMMIT_REF_NAME", "local"),
        "pipeline_source": os.getenv("CI_PIPELINE_SOURCE", "local"),
        "routes": ROUTES,
        "status": "generated",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    content = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    if args.output == "-":
        print(content, end="")
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
