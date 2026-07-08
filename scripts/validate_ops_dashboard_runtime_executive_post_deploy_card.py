#!/usr/bin/env python3
"""Validate Ops Dashboard Runtime Executive post-deploy card."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docs" / "ops-dashboard" / "index.html"

REQUIRED = [
    "runtime-executive-post-deploy-card",
    "Runtime Executive — Post-Deploy público",
    "renderRuntimeExecutivePostDeploy",
    "./data/executive-brief.json",
    "runtime_executive_post_deploy",
    "post-deploy-state",
    "post-deploy-score",
    "post-deploy-failures",
    "post-deploy-links",
    "post-deploy-drilldown",
    "await renderRuntimeExecutivePostDeploy();",
]

FORBIDDEN = [
    "api.github.com",
    "GITHUB_TOKEN",
    "Authorization",
]


def main() -> int:
    if not DASHBOARD.exists():
        raise SystemExit(f"dashboard ausente: {DASHBOARD}")
    html = DASHBOARD.read_text(encoding="utf-8")
    missing = [item for item in REQUIRED if item not in html]
    if missing:
        raise SystemExit(f"card post-deploy ausente/incompleto: {missing}")
    forbidden = [item for item in FORBIDDEN if item in html]
    if forbidden:
        raise SystemExit(f"dashboard contem trecho proibido: {forbidden}")
    if html.count("runtime-executive-post-deploy-card") != 2:
        raise SystemExit("card post-deploy deve aparecer uma vez no section id e uma vez no link/anchor")
    print("ops dashboard runtime executive post-deploy card validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
