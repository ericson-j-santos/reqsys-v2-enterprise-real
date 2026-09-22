#!/usr/bin/env python3
"""Gate preventivo do cutover DEV: PC24x7 é canônico e Fly.io não pode ser fallback.

O objetivo é impedir a regressão que deixou o código novo integrado enquanto a
experiência real do usuário continuava apontando para o runtime legado.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE_DEV_ENTRYPOINT = "https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/"
FORBIDDEN_DEV_RUNTIME_URLS = (
    "https://reqsys-app-dev.fly.dev",
    "https://reqsys-api-dev.fly.dev",
)

CRITICAL_FILES = (
    "frontend/src/constants/ambientesOperacionais.js",
    "frontend/scripts/setup-msal-storage-state.mjs",
    "backend/app/core/config.py",
    ".github/workflows/executive-promotion-advisor-public-smoke.yml",
    ".github/workflows/executive-public-smoke-confirmation.yml",
    ".github/workflows/executive-final-sync-history-public-smoke-trend-public.yml",
    ".github/workflows/noteri-study-mode-dev-reconcile.yml",
    "docs/public-dev-locator/index.html",
)

SIGNED_LOCATOR_CONSUMERS = (
    ".github/workflows/executive-promotion-advisor-public-smoke.yml",
    ".github/workflows/executive-public-smoke-confirmation.yml",
    ".github/workflows/executive-final-sync-history-public-smoke-trend-public.yml",
)


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise RuntimeError(f"missing_required_file:{relative}")
    return path.read_text(encoding="utf-8")


def validate() -> list[str]:
    errors: list[str] = []

    for relative in CRITICAL_FILES:
        raw = read(relative)
        for forbidden in FORBIDDEN_DEV_RUNTIME_URLS:
            if forbidden in raw:
                errors.append(f"legacy_dev_runtime_reference:{relative}:{forbidden}")

    frontend = read("frontend/src/constants/ambientesOperacionais.js")
    if STABLE_DEV_ENTRYPOINT not in frontend:
        errors.append("frontend_dev_entrypoint_not_canonical")
    if "searchParams.set('target', suffix)" not in frontend:
        errors.append("frontend_dev_route_not_forwarded_to_locator")

    locator = read("docs/public-dev-locator/index.html")
    if 'requestedTarget=params.get("target")||"/task-console"' not in locator:
        errors.append("locator_target_forwarding_missing")
    if 'payload.selected_url+target' not in locator:
        errors.append("locator_runtime_redirect_missing")

    for relative in SIGNED_LOCATOR_CONSUMERS:
        raw = read(relative)
        if "resolve_pc24x7_dev_locator.mjs" not in raw:
            errors.append(f"signed_locator_resolution_missing:{relative}")
        if "Runtime legado Fly.io rejeitado" not in raw:
            errors.append(f"legacy_runtime_fail_closed_missing:{relative}")
        if "successo verde" in raw.lower():
            # Evita typo silencioso no texto do próprio gate.
            errors.append(f"invalid_false_green_marker:{relative}")
        if "sucesso verde" not in raw.lower():
            errors.append(f"false_green_enforcement_missing:{relative}")

    study = read(".github/workflows/noteri-study-mode-dev-reconcile.yml")
    trigger = study.split("permissions:", 1)[0]
    if "push:" not in trigger or "- main" not in trigger:
        errors.append("study_mode_post_merge_reconcile_trigger_missing")
    if "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" not in study:
        errors.append("study_mode_pc24x7_runner_missing")

    backend = read("backend/app/core/config.py")
    if STABLE_DEV_ENTRYPOINT not in backend or "same-origin:/api" not in backend:
        errors.append("backend_dev_catalog_not_pc24x7")

    msal = read("frontend/scripts/setup-msal-storage-state.mjs")
    if "resolveDevRuntime" not in msal or "Runtime legado Fly.io é proibido" not in msal:
        errors.append("msal_dev_runtime_not_fail_closed")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for item in errors:
            print(f"DEV_RUNTIME_CUTOVER_BLOCKED:{item}", file=sys.stderr)
        return 2
    print("DEV_RUNTIME_CUTOVER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
