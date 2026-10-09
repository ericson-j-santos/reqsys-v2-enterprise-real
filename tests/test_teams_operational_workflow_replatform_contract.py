from __future__ import annotations

from pathlib import Path


WORKFLOWS = Path('.github/workflows')


def test_recipient_policy_probe_uses_signed_pc24x7_locator() -> None:
    text = (WORKFLOWS / 'teams-recipient-policy-runtime-readiness.yml').read_text(
        encoding='utf-8'
    )

    assert 'resolve_pc24x7_dev_locator.mjs --self-test' in text
    assert 'steps.locator.outputs.base_url' in text
    assert 'https://reqsys-api.fly.dev' not in text
    assert '${{ false && (' not in text


def test_control_center_schedules_only_dev_and_uses_signed_locator() -> None:
    text = (WORKFLOWS / 'teams-notification-control-center-smoke.yml').read_text(
        encoding='utf-8'
    )

    assert 'default: dev' in text
    assert "matrix.environment == 'dev'" in text
    assert 'resolve_pc24x7_dev_locator.mjs --self-test' in text
    assert 'steps.locator.outputs.base_url' in text
    assert 'args+=(--core-api-prefix /api)' in text
    assert 'REQSYS_API_BASE_URL_DEV' not in text


def test_retired_fly_merge_console_workflow_is_removed() -> None:
    assert not (WORKFLOWS / 'dev-merge-console-homologation.yml').exists()


def test_ruleset_validation_builds_accented_contexts_without_source_encoding_risk() -> None:
    text = (WORKFLOWS / 'branch-protection-audit.yml').read_text(encoding='utf-8')

    assert text.count('Validar artefatos de governan{0}a') == 2
    assert text.count('Auditar prote{0}{1}o enterprise da branch') == 2
