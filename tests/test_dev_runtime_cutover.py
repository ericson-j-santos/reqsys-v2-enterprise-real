from scripts.validate_dev_runtime_cutover import (
    CRITICAL_FILES,
    FORBIDDEN_DEV_RUNTIME_URLS,
    ROOT,
    SIGNED_LOCATOR_CONSUMERS,
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


def test_signed_locator_consumers_fail_closed_instead_of_false_green():
    for relative in SIGNED_LOCATOR_CONSUMERS:
        raw = (ROOT / relative).read_text(encoding="utf-8")
        assert "resolve_pc24x7_dev_locator.mjs" in raw
        assert "Runtime legado Fly.io rejeitado" in raw
        assert "sucesso verde" in raw.lower()
        assert "vars.PC24X7_DEV_BASE_URL" not in raw
        assert "vars.PC24X7_DEV_FRONTEND_URL" not in raw


def test_user_journey_uses_same_origin_signed_dev_runtime():
    raw = (ROOT / ".github/workflows/user-journey-acceptance-dev.yml").read_text(encoding="utf-8")
    assert "steps.locator.outputs.base_url" in raw
    assert "printf 'API_URL=%s\\n'" in raw
    assert "printf 'FRONTEND_URL=%s\\n'" in raw
    assert "https://*.trycloudflare.com" in raw


def test_study_mode_reconciles_on_main_after_merge():
    raw = (ROOT / ".github/workflows/noteri-study-mode-dev-reconcile.yml").read_text(encoding="utf-8")
    trigger = raw.split("permissions:", 1)[0]
    assert "push:" in trigger
    assert "- main" in trigger
    assert "pc24x7" in raw

def test_backend_catalog_uses_stable_entrypoint_and_same_origin_api():
    raw = (ROOT / "backend/app/core/config.py").read_text(encoding="utf-8")
    assert STABLE_DEV_ENTRYPOINT in raw
    assert "same-origin:/api" in raw
    assert "reqsys-app-dev.fly.dev" not in raw
    assert "reqsys-api-dev.fly.dev" not in raw

