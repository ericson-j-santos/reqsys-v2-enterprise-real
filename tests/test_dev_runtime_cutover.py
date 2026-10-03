from scripts.validate_dev_runtime_cutover import (
    AUTO_PUBLIC_RUNTIME_EVIDENCE_WORKFLOW,
    CRITICAL_FILES,
    FLY_AUTOMATIC_PROMOTION_WORKFLOW,
    FORBIDDEN_DEV_RUNTIME_URLS,
    ROOT,
    STABLE_DEV_ENTRYPOINT,
    STATIC_DEV_RUNTIME_VARIABLES,
    WSJF_ACCEPTANCE_WORKFLOW,
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
    assert "new URL(rotaRelativa.replace" in raw


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


def test_wsjf_acceptance_uses_signed_locator_same_origin_without_static_urls():
    raw = (ROOT / WSJF_ACCEPTANCE_WORKFLOW).read_text(encoding="utf-8")
    assert "resolve_pc24x7_dev_locator.mjs" in raw
    assert "steps.dev_runtime.outputs.base_url" in raw
    assert "steps.dev_runtime.outputs.frontend_url" in raw
    assert 'echo "API_URL=$resolved_url" >> "$GITHUB_ENV"' in raw
    assert 'echo "FRONTEND_URL=$resolved_url" >> "$GITHUB_ENV"' in raw
    for variable in STATIC_DEV_RUNTIME_VARIABLES:
        assert variable not in raw

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



def test_legacy_fly_promotion_is_manual_only_and_never_routes_dev_to_fly():
    raw = (ROOT / FLY_AUTOMATIC_PROMOTION_WORKFLOW).read_text(encoding="utf-8")
    trigger = raw.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger
    assert "workflow_run:" not in trigger
    assert "schedule:" not in trigger
    assert "Validate DEV via PC24x7 public tunnel" in raw
    assert "REQSYS_DEV_RUNTIME_PROVIDER" not in raw
    assert "Capture DEV via Fly" not in raw
    assert "Promote DEV via Fly" not in raw
    assert "needs.resolve.outputs.dev_provider" not in raw


def test_auto_public_runtime_evidence_is_pc24x7_only_after_blocking_post_merge():
    raw = (ROOT / AUTO_PUBLIC_RUNTIME_EVIDENCE_WORKFLOW).read_text(encoding="utf-8")
    trigger = raw.split("permissions:", 1)[0]
    assert "Main Post-Merge Validation" in trigger
    assert "Fly Automatic Environment Promotion" not in raw
    assert "resolve_pc24x7_dev_locator.mjs" in raw
    assert "github.event.workflow_run.event" in raw
    assert "workflow_dispatch" in raw
    assert "Runtime DEV legado Fly.io rejeitado" in raw
    assert "REQSYS_DEV_RUNTIME_PROVIDER" not in raw
    assert "PC24X7_DEV_BASE_URL" not in raw
    assert "PC24X7_DEV_FRONTEND_URL" not in raw
    assert "reqsys-api.fly.dev" not in raw
