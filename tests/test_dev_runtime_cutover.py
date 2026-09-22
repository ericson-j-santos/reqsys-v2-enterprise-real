from pathlib import Path

from scripts.validate_dev_runtime_cutover import (
    CRITICAL_FILES,
    FORBIDDEN_DEV_RUNTIME_URLS,
    ROOT,
    STABLE_DEV_ENTRYPOINT,
    validate,
)


def test_dev_runtime_cutover_gate_passes_repository_state():
    assert validate() == []


def test_critical_operational_files_do_not_reference_legacy_dev_fly():
    for relative in CRITICAL_FILES:
        raw = (ROOT / relative).read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_DEV_RUNTIME_URLS:
            assert forbidden not in raw, relative


def test_frontend_uses_stable_pc24x7_entrypoint():
    raw = (ROOT / "frontend/src/constants/ambientesOperacionais.js").read_text(encoding="utf-8")
    assert STABLE_DEV_ENTRYPOINT in raw
    assert "searchParams.set('target', suffix)" in raw


def test_public_smokes_fail_closed_instead_of_false_green():
    workflows = (
        ".github/workflows/executive-promotion-advisor-public-smoke.yml",
        ".github/workflows/executive-public-smoke-confirmation.yml",
        ".github/workflows/executive-final-sync-history-public-smoke-trend-public.yml",
    )
    for relative in workflows:
        raw = (ROOT / relative).read_text(encoding="utf-8")
        assert "resolve_pc24x7_dev_locator.mjs" in raw
        assert "Runtime legado Fly.io rejeitado" in raw
        assert "sucesso verde" in raw.lower()


def test_study_mode_reconciles_on_main_after_merge():
    raw = (ROOT / ".github/workflows/noteri-study-mode-dev-reconcile.yml").read_text(encoding="utf-8")
    trigger = raw.split("permissions:", 1)[0]
    assert "push:" in trigger
    assert "- main" in trigger
    assert "pc24x7" in raw
