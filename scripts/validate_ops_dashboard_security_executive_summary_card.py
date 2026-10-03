#!/usr/bin/env python3
"""Validate Ops Dashboard Security Executive Summary card."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docs" / "ops-dashboard" / "index.html"
DATA = ROOT / "docs" / "ops-dashboard" / "data" / "security-executive-summary.json"

REQUIRED_HTML = [
    "security-executive-summary-card",
    "Segurança — resumo executivo dos scanners",
    "renderSecurityExecutiveSummary",
    "./data/security-executive-summary.json",
    "security-executive-summary.md",
    "security-summary-state",
    "security-summary-score",
    "security-summary-risk",
    "security-summary-production-blocked",
    "security-summary-critical",
    "security-summary-high",
    "security-summary-medium",
    "security-summary-low",
    "security-summary-scanner-rows",
    "security-summary-drilldown",
    "security-summary-details",
    "security_executive_summary",
    "missing_scanners",
    "production_blocked",
    "await renderSecurityExecutiveSummary();",
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
    missing = [item for item in REQUIRED_HTML if item not in html]
    if missing:
        raise SystemExit(f"card security executive summary ausente/incompleto: {missing}")
    forbidden = [item for item in FORBIDDEN if item in html]
    if forbidden:
        raise SystemExit(f"dashboard contem trecho proibido: {forbidden}")
    if html.count("security-executive-summary-card") < 2:
        raise SystemExit("card security executive summary deve ter section id e pelo menos um link/anchor")
    if DATA.exists():
        import json

        payload = json.loads(DATA.read_text(encoding="utf-8"))
        if payload.get("kind") != "security_executive_summary":
            raise SystemExit("security-executive-summary.json com kind invalido")
        if "overall" not in payload or "totals" not in payload or "scanners" not in payload:
            raise SystemExit("security-executive-summary.json sem chaves executivas obrigatorias")
    print("ops dashboard security executive summary card validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
