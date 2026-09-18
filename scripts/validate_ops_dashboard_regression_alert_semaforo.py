#!/usr/bin/env python3
"""Validate main Ops Dashboard semaforo integration for Runtime Executive regression alert."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "docs" / "ops-dashboard" / "index.html"

REQUIRED = [
    "runtime-regression-alert-semaforo-card",
    "Semáforo Executivo — Regressão temporal Runtime Executive",
    "renderRuntimeRegressionAlertSemaforo",
    "../artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json",
    "semaforo-regression-status",
    "semaforo-regression-risk",
    "semaforo-regression-blocked",
    "semaforo-regression-violations",
    "semaforo-regression-details",
    "await renderRuntimeRegressionAlertSemaforo();",
    "document.getElementById('overall').innerHTML = '<span class=\"status blocked\">blocked</span>';",
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
        raise SystemExit(f"semaforo regression alert ausente/incompleto: {missing}")
    forbidden = [item for item in FORBIDDEN if item in html]
    if forbidden:
        raise SystemExit(f"dashboard contem trecho proibido: {forbidden}")
    print("ops dashboard regression alert semaforo validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
