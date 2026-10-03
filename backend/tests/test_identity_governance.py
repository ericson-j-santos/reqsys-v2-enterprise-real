from datetime import datetime, timezone

import pytest

from app.core.identity_governance import (
    ApplicationIdentityProfile,
    ApplicationIdentityRegistry,
    DataClassification,
    IdentityGovernanceError,
)


def _profile(**overrides):
    data = {
        "name": "reqsys-dev-login",
        "environment": "development",
        "purpose": "interactive-login",
        "data_classification": DataClassification.INTERNAL,
        "tenant_id": "tenant-a",
        "client_id": "client-login-dev",
        "current_secret_ref": "vault://reqsys/dev/login/current",
        "next_secret_ref": "vault://reqsys/dev/login/next",
        "rotated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "max_age_days": 60,
    }
    data.update(overrides)
    return ApplicationIdentityProfile(**data)


def test_resolve_requires_exact_environment_purpose_and_classification():
    registry = ApplicationIdentityRegistry([_profile()])

    resolved = registry.resolve(
        environment="dev",
        purpose="interactive-login",
        data_classification="internal",
        now=datetime(2026, 8, 18, tzinfo=timezone.utc),
    )

    assert resolved.client_id == "client-login-dev"

    with pytest.raises(IdentityGovernanceError):
        registry.resolve(
            environment="production",
            purpose="interactive-login",
            data_classification="internal",
            now=datetime(2026, 8, 18, tzinfo=timezone.utc),
        )


def test_expired_credential_is_fail_closed():
    registry = ApplicationIdentityRegistry([_profile(max_age_days=10)])

    with pytest.raises(IdentityGovernanceError, match="expirou"):
        registry.resolve(
            environment="development",
            purpose="interactive-login",
            data_classification="internal",
            now=datetime(2026, 8, 18, tzinfo=timezone.utc),
        )


def test_rotation_report_warns_before_expiration():
    registry = ApplicationIdentityRegistry([_profile(max_age_days=30)])

    report = registry.rotation_report(
        now=datetime(2026, 8, 18, tzinfo=timezone.utc),
        warning_days=14,
    )

    assert report[0]["rotation_required"] is True
    assert report[0]["expired"] is False


def test_raw_secret_is_rejected():
    with pytest.raises(IdentityGovernanceError, match="nunca o segredo em claro"):
        ApplicationIdentityRegistry([_profile(current_secret_ref="super-secret-value")])


def test_protected_data_requires_dedicated_application_registration():
    first = _profile(
        name="reqsys-dev-teams",
        purpose="teams-proactive-messaging",
        data_classification=DataClassification.CONFIDENTIAL,
        client_id="shared-client",
    )
    second = _profile(
        name="reqsys-dev-sharepoint",
        purpose="sharepoint-write",
        data_classification=DataClassification.RESTRICTED,
        client_id="shared-client",
        current_secret_ref="vault://reqsys/dev/sharepoint/current",
        next_secret_ref="vault://reqsys/dev/sharepoint/next",
    )

    with pytest.raises(IdentityGovernanceError, match="App Registration dedicada"):
        ApplicationIdentityRegistry([first, second])


def test_duplicate_context_is_rejected():
    with pytest.raises(IdentityGovernanceError, match="Perfil duplicado"):
        ApplicationIdentityRegistry(
            [
                _profile(),
                _profile(
                    name="duplicate",
                    client_id="another-client",
                    current_secret_ref="vault://reqsys/dev/login-2/current",
                    next_secret_ref="vault://reqsys/dev/login-2/next",
                ),
            ]
        )
