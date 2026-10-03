from scripts.inject_ops_dashboard_runtime_executive_post_deploy_card import (
    DASHBOARD,
    SECTION_MARKER,
    inject_dashboard,
)


def test_injection_adds_exact_section_and_is_idempotent():
    source = DASHBOARD.read_text(encoding="utf-8")
    patched = inject_dashboard(source)

    assert SECTION_MARKER in patched
    assert "Runtime Executive — Post-Deploy público" in patched
    assert patched.count(SECTION_MARKER) == 1
    assert inject_dashboard(patched) == patched


def test_link_reference_does_not_count_as_existing_section():
    source = DASHBOARD.read_text(encoding="utf-8")
    without_section = source.replace(
        '<section class="card" id="runtime-executive-post-deploy-card">',
        '<!-- section intentionally absent for regression control -->',
    ).replace(
        "Runtime Executive — Post-Deploy público",
        "Runtime Executive post-deploy placeholder",
    )

    patched = inject_dashboard(without_section)

    assert '<section class="card" id="runtime-executive-post-deploy-card">' in patched
    assert "Runtime Executive — Post-Deploy público" in patched
