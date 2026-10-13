"""Contratos de regressão da prova pública de navegador da lupa DEV.

O sucesso do browser anônimo NÃO substitui a integridade do runtime
ou a sessão Microsoft delegada validada pelo job autenticado.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "validacao-acessos.yml"
SPEC = ROOT / "frontend" / "tests" / "e2e" / "global-search-published.spec.js"


def _jobs(text: str) -> tuple[str, str, str]:
    validar, other = text.split("\n  anonymous:\n", 1)
    anonymous, authenticated = other.split("\n  authenticated:\n", 1)
    return validar, anonymous, authenticated


def _secure_contract(text: str) -> bool:
    try:
        validar, anonymous, authenticated = _jobs(text)
    except ValueError:
        return False
    return all((
        'if runtime_sha_required and observed != expected:' in validar,
        'raise SystemExit("build_sha_mismatch")' in validar,
        "always() && github.event_name == 'workflow_dispatch'" in anonymous,
        "needs: validar-acessos" in anonymous,
        "published_runtime_sha_mismatch" not in anonymous,
        "Exercise real published browser (no mocks)" in anonymous,
        "frontend/test-results/**/public-login.png" in anonymous,
        "if-no-files-found: error" in anonymous,
        "needs: [validar-acessos, anonymous]" in authenticated,
        "inputs.mode == 'authenticated'" in authenticated,
        "MSAL_DELEGATED_SESSION_MISSING" in authenticated,
        "MSAL_DELEGATED_SESSION_EXPIRED_OR_INVALID" in authenticated,
        "Test real search after Entra ID authentication" in authenticated,
    ))


def test_browser_anonymous_is_observable_despite_runtime_sha_drift():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert _secure_contract(text)


def test_public_login_evidence_never_includes_authenticated_tokens():
    text = SPEC.read_text(encoding="utf-8")
    _, anonymous, authenticated = _jobs(WORKFLOW.read_text(encoding="utf-8"))
    assert "testInfo.outputPath('public-login.png')" in text
    assert "Preserve screenshot of anonymous Pages login" in anonymous
    assert "frontend/test-results/**/public-login.png" not in authenticated
    assert "upload-artifact" not in authenticated
    assert "Validate existing Microsoft session without logging secrets" in authenticated


def test_contract_rejects_accidental_ungated_authenticated_job():
    current = WORKFLOW.read_text(encoding="utf-8")
    assert _secure_contract(current)
    broken = current.replace(
        "needs: [validar-acessos, anonymous]",
        "needs: anonymous",
        1,
    )
    assert broken != current
    assert not _secure_contract(broken)


def test_contract_rejects_browser_skipping_on_runtime_failure():
    current = WORKFLOW.read_text(encoding="utf-8")
    assert _secure_contract(current)
    broken = current.replace(
        "always() && github.event_name == 'workflow_dispatch'",
        "github.event_name == 'workflow_dispatch'",
        1,
    )
    assert broken != current
    assert not _secure_contract(broken)

def _public_auth_evidence_contract(text: str) -> bool:
    try:
        screenshot = text.index("await page.screenshot({")
        flags = text.index("check: 'public_auth_flags'")
        demo_assertion = text.index("expect(config?.demo_login_enabled).toBe(false)")
    except ValueError:
        return False
    return (
        screenshot < flags < demo_assertion
        and "mask: [page.locator('.login-card input')]" in text
        and "new URL(response.url()).pathname.endsWith('/api/v1/auth/config')" in text
        and "expect(signedRuntimeOrigin).toBe(true)" in text
        and "expect(config?.azure_enabled).toBe(true)" in text
        and "await expect(page.getByRole('button', { name: /entrar \\(demo\\)/i })).toHaveCount(0)" in text
    )


def test_public_auth_flags_recorded_and_screenshot_masked_before_failure():
    assert _public_auth_evidence_contract(SPEC.read_text(encoding='utf-8'))


def test_public_auth_evidence_contract_detects_regressions():
    original = SPEC.read_text(encoding='utf-8')
    assert _public_auth_evidence_contract(original)
    assert not _public_auth_evidence_contract(original.replace(
        "expect(config?.demo_login_enabled).toBe(false)",
        "expect(config?.demo_login_enabled).toBe(true)",
        1,
    ))
    assert not _public_auth_evidence_contract(original.replace(
        "mask: [page.locator('.login-card input')]",
        "mask: []",
        1,
    ))
    assert not _public_auth_evidence_contract(original.replace(
        "await page.screenshot({",
        "// screenshot removed",
        1,
    ))
