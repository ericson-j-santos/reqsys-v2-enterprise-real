from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scripts.credential_control_plane_lifecycle import (
    LifecycleError,
    RotationResult,
    SecretMetadata,
    build_evidence,
    build_plan,
    execute_plan,
    validate_policy,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def base_policy(provider: str = "gitlab"):
    item = {
        "credential_id": "gitlab-main-mirror" if provider == "gitlab" else "fly-api-dev-deploy",
        "provider": provider,
        "secret_name": "main-token",
        "enabled": True,
        "rotation": {
            "strategy": "gitlab_self_rotate" if provider == "gitlab" else "fly_replace_deploy_token",
            "interval_days": 30,
            "warning_days": 7,
            "expires_in_days": 30,
        },
        "target": {"project": "owner/repo"} if provider == "gitlab" else {"app": "reqsys-api-dev"},
    }
    if provider == "fly":
        item["issuer_secret_name"] = "fly-issuer"
    return {
        "contract": "reqsys-credential-control-plane-lifecycle",
        "execution": {
            "secret_store": {
                "provider": "azure_key_vault",
                "authentication": "github_oidc",
                "vault_name_env": "REQSYS_KEY_VAULT_NAME",
                "allow_github_secret_fallback": False,
            },
            "identity_federation": {
                "github_actions": {
                    "mode": "oidc",
                    "long_lived_github_token_required": False,
                }
            },
        },
        "managed_credentials": [item],
    }


class FakeStore:
    def __init__(self, metadata=None, secrets=None):
        self._metadata = metadata or {}
        self._secrets = secrets or {}
        self.writes = []

    def metadata(self, name):
        return self._metadata.get(name, SecretMetadata(name=name, exists=False))

    def read(self, name):
        if name not in self._secrets:
            raise LifecycleError(f"missing {name}")
        return self._secrets[name]

    def write(self, name, value, *, expires_at, tags):
        self.writes.append((name, value, expires_at, tags))
        self._secrets[name] = value
        self._metadata[name] = SecretMetadata(
            name=name,
            exists=True,
            enabled=True,
            updated_at=NOW,
            expires_at=expires_at,
            tags=tags,
        )


class FakeGitLab:
    def __init__(self):
        self.validated = False

    def rotate_self(self, project, current_token, *, expires_at):
        assert project == "owner/repo"
        assert current_token == "old"
        return "new", "42"

    def validate_repository(self, project, token):
        assert token == "new"
        self.validated = True


class FakeFly:
    def __init__(self):
        self.revoked = []
        self.validated = False

    def create_deploy_token(self, *, app, issuer_token, name, expires_in_days):
        assert app == "reqsys-api-dev"
        assert issuer_token == "issuer"
        return "new-fly", "new-id"

    def validate_app(self, *, app, token):
        assert token == "new-fly"
        self.validated = True

    def revoke(self, *, token_id, issuer_token):
        self.revoked.append((token_id, issuer_token))


def test_policy_rejeita_fallback_para_github_secret():
    policy = base_policy()
    policy["execution"]["secret_store"]["allow_github_secret_fallback"] = True
    with pytest.raises(LifecycleError, match="allow_github_secret_fallback"):
        validate_policy(policy)


def test_policy_rejeita_token_github_de_longa_duracao():
    policy = base_policy()
    policy["execution"]["identity_federation"]["github_actions"]["long_lived_github_token_required"] = True
    with pytest.raises(LifecycleError, match="long_lived_github_token_required"):
        validate_policy(policy)


def test_plan_gitlab_saudavel_fora_da_janela():
    store = FakeStore(metadata={
        "main-token": SecretMetadata(
            name="main-token", exists=True, enabled=True,
            updated_at=NOW - timedelta(days=5), expires_at=NOW + timedelta(days=25),
            tags={"rotated_at": (NOW - timedelta(days=5)).isoformat()},
        )
    })
    plan = build_plan(base_policy(), store, now=NOW)
    assert plan["status"] == "HEALTHY"
    assert plan["credentials"][0]["action"] == "NONE"


def test_plan_gitlab_exige_bootstrap_quando_secret_nao_existe():
    plan = build_plan(base_policy(), FakeStore(), now=NOW)
    assert plan["status"] == "BLOCKED"
    assert plan["credentials"][0]["status"] == "BOOTSTRAP_REQUIRED"


def test_plan_fly_permite_create_quando_issuer_existe():
    policy = base_policy("fly")
    store = FakeStore(metadata={"fly-issuer": SecretMetadata(name="fly-issuer", exists=True, enabled=True)})
    plan = build_plan(policy, store, now=NOW)
    assert plan["status"] == "ACTION_REQUIRED"
    assert plan["credentials"][0]["action"] == "CREATE"


def test_plan_fly_bloqueia_rotacao_sem_id_para_revogacao_segura():
    policy = base_policy("fly")
    store = FakeStore(metadata={
        "main-token": SecretMetadata(
            name="main-token", exists=True, enabled=True,
            updated_at=NOW - timedelta(days=29), expires_at=NOW + timedelta(days=1),
            tags={"rotated_at": (NOW - timedelta(days=29)).isoformat()},
        ),
        "fly-issuer": SecretMetadata(name="fly-issuer", exists=True, enabled=True),
    })
    plan = build_plan(policy, store, now=NOW)
    assert plan["status"] == "BLOCKED"
    assert plan["credentials"][0]["reason"] == "provider_token_id_missing_for_safe_revoke"


def test_plan_gitlab_expirado_exige_novo_bootstrap():
    store = FakeStore(metadata={
        "main-token": SecretMetadata(
            name="main-token", exists=True, enabled=True,
            updated_at=NOW - timedelta(days=31), expires_at=NOW - timedelta(minutes=1),
            tags={"rotated_at": (NOW - timedelta(days=31)).isoformat()},
        )
    })
    plan = build_plan(base_policy(), store, now=NOW)
    assert plan["status"] == "BLOCKED"
    assert plan["credentials"][0]["status"] == "BOOTSTRAP_REQUIRED"
    assert plan["credentials"][0]["reason"] == "gitlab_token_expired_self_rotate_unavailable"


def test_plan_fly_bloqueia_quando_issuer_indisponivel():
    policy = base_policy("fly")
    store = FakeStore(metadata={
        "main-token": SecretMetadata(
            name="main-token", exists=True, enabled=True,
            updated_at=NOW - timedelta(days=29), expires_at=NOW + timedelta(days=1),
            tags={
                "rotated_at": (NOW - timedelta(days=29)).isoformat(),
                "provider_token_id": "old-id",
            },
        )
    })
    plan = build_plan(policy, store, now=NOW)
    assert plan["status"] == "BLOCKED"
    assert plan["credentials"][0]["reason"] == "fly_issuer_unavailable"


def test_execute_gitlab_persiste_novo_token_e_valida(monkeypatch):
    policy = base_policy()
    store = FakeStore(
        metadata={
            "main-token": SecretMetadata(
                name="main-token", exists=True, enabled=True,
                updated_at=NOW - timedelta(days=29), expires_at=NOW + timedelta(days=1),
                tags={"rotated_at": (NOW - timedelta(days=29)).isoformat()},
            )
        },
        secrets={"main-token": "old"},
    )
    plan = build_plan(policy, store, now=NOW)
    monkeypatch.setenv("REQSYS_CREDENTIAL_MUTATION_ENABLED", "true")
    adapter = FakeGitLab()
    results = execute_plan(policy, store, plan, now=NOW, gitlab=adapter, fly=FakeFly())
    assert results == [RotationResult(
        "gitlab-main-mirror", "gitlab", "ROTATED",
        "self_rotate_persisted_and_validated", "42", NOW + timedelta(days=30),
    )]
    assert store.writes[0][1] == "new"
    assert adapter.validated is True


def test_execute_fly_valida_persiste_e_revoga_anterior(monkeypatch):
    policy = base_policy("fly")
    store = FakeStore(
        metadata={
            "main-token": SecretMetadata(
                name="main-token", exists=True, enabled=True,
                updated_at=NOW - timedelta(days=29), expires_at=NOW + timedelta(days=1),
                tags={
                    "rotated_at": (NOW - timedelta(days=29)).isoformat(),
                    "provider_token_id": "old-id",
                },
            ),
            "fly-issuer": SecretMetadata(name="fly-issuer", exists=True, enabled=True),
        },
        secrets={"fly-issuer": "issuer", "main-token": "old-fly"},
    )
    plan = build_plan(policy, store, now=NOW)
    monkeypatch.setenv("REQSYS_CREDENTIAL_MUTATION_ENABLED", "true")
    adapter = FakeFly()
    results = execute_plan(policy, store, plan, now=NOW, gitlab=FakeGitLab(), fly=adapter)
    assert results[0].status == "ROTATED"
    assert store.writes[0][1] == "new-fly"
    assert adapter.validated is True
    assert adapter.revoked == [("old-id", "issuer")]


def test_execute_bloqueado_sem_feature_flag(monkeypatch):
    monkeypatch.delenv("REQSYS_CREDENTIAL_MUTATION_ENABLED", raising=False)
    with pytest.raises(LifecycleError, match="Mutação bloqueada"):
        execute_plan(base_policy(), FakeStore(), {"credentials": []}, now=NOW)


def test_evidence_validate_valido_retorna_pass():
    evidence = build_evidence(mode="validate", correlation_id="cid-validate", plan={"status": "VALID"})
    assert evidence["status"] == "PASS"


def test_evidence_nunca_contem_valor_de_secret():
    evidence = build_evidence(
        mode="execute",
        correlation_id="cid-1",
        plan={"status": "HEALTHY", "summary": {}},
        results=[RotationResult("x", "gitlab", "ROTATED", "ok", "42", NOW)],
    )
    assert "old-token" not in str(evidence).lower()
    assert evidence["security"]["secret_values_exposed"] is False
