"""Contract and failure-ordering checks for the bounded DEV cutover controller."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json

import pytest

pytest.importorskip("cryptography", reason="requires the dedicated DEV candidate contract environment")

from scripts import self_hosted_dev_candidate_control as candidate

SHA = "1" * 40
BACKUP = "2" * 64
NOW = datetime(2026, 10, 3, 23, 30, tzinfo=timezone.utc)
DB = {
    "database": "reqsys", "container_id": "a" * 64,
    "postgres_system_identifier": "7541234567890123456",
}
CONFIG = {
    "azure_tenant_id": "11111111-1111-1111-1111-111111111111",
    "azure_client_id": "22222222-2222-2222-2222-222222222222",
    "expected_redirect_uri": "https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/auth/callback.html",
    "demo_login_enabled": False,
}


def _seal(proof):
    proof["proof_integrity_sha256"] = candidate.integrity(proof)
    return proof


def _restore():
    return _seal({
        "schema_version": "1", "contract": "reqsys-current-postgres-restore",
        "source_engine": "postgresql", "status": "verified",
        "host": "DESKTOP-PDQK954", "project": "reqsys-dev-selfhosted",
        "instance": "pc24x7-selfhost-dev-v1", "target_sha": SHA,
        "source_project": "wt-pc24x7-piloto", "source_sha256": BACKUP,
        "verified_at": NOW.isoformat(), "source_rows": 3, "copied_rows": 3,
        "table_counts": {"usuarios": 3},
        "backup_source_identity": {
            "api_container_id": "b" * 64, "database_container_id": "c" * 64,
            "postgres_system_identifier": "7531234567890123456",
            "database": "reqsys", "role": "reqsys_app",
        },
        "database_identity": dict(DB),
        "archive_validated": True, "content_digests_match": True,
        "independent_readback": True, "migration_committed": True,
        "sequences_verified": True, "schema_inventory_verified": True,
        "runtime_keys_preserved": True,
        "private_archive_content": {
            "usuarios": {"count": 3, "columns": ["id"], "digest": "d" * 64},
        },
        "private_archive_sequences": {"usuarios_id_seq": ["3", True]},
        "private_restored_schema": {
            "tables": {"usuarios": ["id"]}, "sequences": ["usuarios_id_seq"],
            "foreign_namespaces": 0, "other_objects": 0,
        },
        "source_writes_frozen": False, "current_source_freshness_verified": False,
        "authenticated_flow_verified": False, "public_ingress_verified": False,
        "usable": False,
    })


def _auth(restore):
    return _seal({
        "schema_version": "1", "contract": "reqsys-self-hosted-dev-azure-auth",
        "host": "DESKTOP-PDQK954", "project": "reqsys-dev-selfhosted",
        "instance": "pc24x7-selfhost-dev-v1", "source_sha": SHA,
        "verified_at": NOW.isoformat(), "verification_scope": "backend_azure_session",
        "authenticated_flow_verified": True,
        "ui_interactive_callback_verified": False,
        "demo_login_enabled": False,
        "azure_tenant_id": CONFIG["azure_tenant_id"],
        "azure_client_id": CONFIG["azure_client_id"],
        "expected_redirect_uri": CONFIG["expected_redirect_uri"],
        "auth_config_sha256": candidate.digest(CONFIG),
        "restore_proof_sha256": candidate.digest(restore),
        "azure_login_status": 200, "api_session_status": 200,
        "anonymous_session_rejected": True, "invalid_azure_signature_rejected": True,
    })


def _freeze(restore, auth):
    return _seal({
        "schema_version": "1", "contract": "reqsys-dev-authoritative-source-freeze",
        "status": "verified", "host": "DESKTOP-PDQK954",
        "project": "reqsys-dev-selfhosted", "instance": "pc24x7-selfhost-dev-v1",
        "target_sha": SHA, "source_project": "wt-pc24x7-piloto",
        "source_api_container_id": restore["backup_source_identity"]["api_container_id"],
        "source_sha256": BACKUP, "restore_proof_sha256": candidate.digest(restore),
        "auth_proof_sha256": candidate.digest(auth),
        "source_writes_frozen": True, "consistent_backup_verified": True,
        "supervisor_lease_verified": True, "rollback_protected": True,
        "verified_at": NOW.isoformat(), "final_backup_verified_at": NOW.isoformat(),
    })


def _receipt(restore, auth, freeze):
    return _seal({
        "schema_version": "1", "contract": "reqsys-dev-public-cutover-activation",
        "status": "verified", "host": "DESKTOP-PDQK954",
        "project": "reqsys-dev-selfhosted", "instance": "pc24x7-selfhost-dev-v1",
        "source_sha": SHA, "restore_proof_sha256": candidate.digest(restore),
        "auth_proof_sha256": candidate.digest(auth),
        "source_freeze_proof_sha256": candidate.digest(freeze),
        "database_identity": dict(DB), "auth_config_sha256": candidate.digest(CONFIG),
        "candidate_public_ingress_verified": True,
        "source_writes_frozen": True, "runtime_keys_preserved": True,
        "backend_authenticated": True, "ui_interactive_callback_verified": False,
        "activated_at": NOW.isoformat(),
    })


@pytest.fixture
def proofs():
    restore = _restore()
    auth = _auth(restore)
    freeze = _freeze(restore, auth)
    return restore, auth, freeze, _receipt(restore, auth, freeze)


def test_valid_complete_proof_chain_is_bound_to_one_dev_runtime(proofs):
    restore, auth, freeze, receipt = proofs
    assert candidate.validate_restore(restore, SHA, NOW) == restore
    assert candidate.validate_auth(auth, restore, CONFIG, SHA, NOW) == auth
    assert candidate.validate_freeze(freeze, restore, auth, SHA, NOW) == freeze
    assert candidate.validate_receipt(receipt, restore, auth, CONFIG, SHA, NOW) == receipt


@pytest.mark.parametrize("key,value", [
    ("contract", "reqsys-sqlite-postgres-import"),
    ("source_engine", "sqlite"), ("host", "NOTERI"),
    ("project", "reqsys-live"), ("instance", "other"),
    ("target_sha", "3" * 40), ("source_sha256", "invalid"),
    ("source_project", "production"),
    ("archive_validated", False), ("content_digests_match", False),
    ("independent_readback", False), ("migration_committed", False),
    ("sequences_verified", False), ("schema_inventory_verified", False),
    ("runtime_keys_preserved", False),
])
def test_altered_restore_proof_still_blocks_with_recomputed_integrity(proofs, key, value):
    restore = copy.deepcopy(proofs[0])
    restore[key] = value
    _seal(restore)
    with pytest.raises(candidate.Error):
        candidate.validate_restore(restore, SHA, NOW)


def test_restore_digest_cannot_be_replaced_by_true_flags(proofs):
    restore = copy.deepcopy(proofs[0])
    restore["verified_at"] = (NOW - timedelta(minutes=61)).isoformat()
    with pytest.raises(candidate.Error):
        candidate.validate_restore(restore, SHA, NOW, fresh=False)


@pytest.mark.parametrize("key,value", [
    ("verification_scope", "auth_config_only"),
    ("authenticated_flow_verified", False),
    ("azure_login_status", 401), ("api_session_status", 401),
    ("anonymous_session_rejected", False),
    ("invalid_azure_signature_rejected", False),
    ("demo_login_enabled", True), ("source_sha", "3" * 40),
    ("restore_proof_sha256", "f" * 64), ("auth_config_sha256", "e" * 64),
    ("azure_tenant_id", "33333333-3333-3333-3333-333333333333"),
    ("azure_client_id", "44444444-4444-4444-4444-444444444444"),
    ("expected_redirect_uri", "http://localhost:18080/auth/callback.html"),
])
def test_auth_requires_real_backend_session_and_exact_public_configuration(proofs, key, value):
    restore, auth, _, _ = copy.deepcopy(proofs)
    auth[key] = value
    _seal(auth)
    with pytest.raises(candidate.Error):
        candidate.validate_auth(auth, restore, CONFIG, SHA, NOW)


@pytest.mark.parametrize("key,value", [
    ("source_writes_frozen", False), ("consistent_backup_verified", False),
    ("supervisor_lease_verified", False), ("rollback_protected", False),
    ("source_api_container_id", "e" * 64),
    ("source_sha256", "e" * 64), ("source_project", "reqsys-live"),
    ("target_sha", "3" * 40), ("restore_proof_sha256", "e" * 64),
    ("auth_proof_sha256", "e" * 64),
])
def test_cutover_requires_an_exact_authoritative_freeze(proofs, key, value):
    restore, auth, freeze, _ = copy.deepcopy(proofs)
    freeze[key] = value
    _seal(freeze)
    with pytest.raises(candidate.Error):
        candidate.validate_freeze(freeze, restore, auth, SHA, NOW)


@pytest.mark.parametrize("name", ["verified_at", "final_backup_verified_at"])
@pytest.mark.parametrize("delta", [timedelta(seconds=301), timedelta(seconds=-1)])
def test_freeze_evidence_is_fresh_and_never_from_the_future(proofs, name, delta):
    restore, auth, freeze, _ = copy.deepcopy(proofs)
    freeze[name] = (NOW - delta).isoformat()
    _seal(freeze)
    with pytest.raises(candidate.Error):
        candidate.validate_freeze(freeze, restore, auth, SHA, NOW)


@pytest.mark.parametrize("key,value", [
    ("source_sha", "3" * 40), ("project", "reqsys-live"),
    ("restore_proof_sha256", "e" * 64), ("auth_proof_sha256", "e" * 64),
    ("auth_config_sha256", "e" * 64),
    ("candidate_public_ingress_verified", False), ("source_writes_frozen", False),
    ("runtime_keys_preserved", False), ("backend_authenticated", False),
])
def test_receipt_cannot_authorize_a_different_or_unverified_runtime(proofs, key, value):
    restore, auth, _, receipt = copy.deepcopy(proofs)
    receipt[key] = value
    _seal(receipt)
    with pytest.raises(candidate.Error):
        candidate.validate_receipt(receipt, restore, auth, CONFIG, SHA, NOW)


@pytest.mark.parametrize("field", ["container_id", "postgres_system_identifier"])
def test_receipt_database_identity_is_preserved_across_maintenance(proofs, field):
    restore, auth, _, receipt = copy.deepcopy(proofs)
    receipt["database_identity"][field] = "9" * 64 if field == "container_id" else "9999"
    _seal(receipt)
    with pytest.raises(candidate.Error):
        candidate.validate_receipt(receipt, restore, auth, CONFIG, SHA, NOW)


def test_maintenance_accepts_historical_authentication_without_claiming_a_new_login(proofs):
    restore, auth, _, receipt = proofs
    later = NOW + timedelta(days=30)
    assert candidate.validate_restore(restore, SHA, later, fresh=False) == restore
    assert candidate.validate_auth(auth, restore, CONFIG, SHA, later, fresh=False) == auth
    assert candidate.validate_receipt(receipt, restore, auth, CONFIG, SHA, later) == receipt
    with pytest.raises(candidate.Error):
        candidate.validate_auth(auth, restore, CONFIG, SHA, later)


@pytest.mark.parametrize("flag", [
    "anonymous_session_rejected", "invalid_azure_signature_rejected",
])
def test_auth_negative_controls_cannot_be_omitted(proofs, flag):
    restore, auth, _, _ = copy.deepcopy(proofs)
    del auth[flag]
    _seal(auth)
    with pytest.raises(candidate.Error):
        candidate.validate_auth(auth, restore, CONFIG, SHA, NOW)


def _activation_controller(tmp_path, monkeypatch, proofs, *, fail_key=False, fail_publish=False):
    restore, auth, freeze, _ = proofs
    events = []
    written = {}

    class Private:
        def check(self, path):
            pass

        def preserving(self, path, raw):
            events.append(path.name)
            written[path.name] = raw

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    class Locator:
        @staticmethod
        def ensure_identity():
            events.append("key_fidelity")
            if fail_key:
                raise candidate.Error("test_pinned_locator_identity_missing")

    controller = object.__new__(candidate.Controller)
    controller.sha = SHA
    controller.root = tmp_path / "SelfHostedDev"
    controller.marker = tmp_path / "RuntimeSupervisor" / "self-hosted-dev-active.json"
    controller.private = Private()
    monkeypatch.setattr(candidate, "datetime", Clock)
    monkeypatch.setattr(candidate, "_locator", lambda: Locator())
    monkeypatch.setattr(controller, "proofs", lambda fresh: (restore, auth, CONFIG))
    monkeypatch.setattr(controller, "local_ready", lambda: {})
    monkeypatch.setattr(controller, "verify_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(controller, "read_private", lambda name: freeze)
    monkeypatch.setattr(controller, "inspect", lambda name: {
        "Id": freeze["source_api_container_id"],
        "Config": {"Labels": {
            "com.docker.compose.project": "wt-pc24x7-piloto",
            "com.docker.compose.service": "api",
        }},
        "State": {"Running": False},
    })
    monkeypatch.setattr(controller, "candidates", lambda apply: [
        "https://primary.trycloudflare.com", "https://secondary.trycloudflare.com",
    ])

    def publish(urls):
        events.append("publish")
        if fail_publish:
            raise candidate.Error("test_locator_publication_failed")
        return {"published": True}

    monkeypatch.setattr(controller, "sign_publish", publish)
    return controller, events, written


def test_activation_marker_requires_key_fidelity_and_receipt_before_publication(
    tmp_path, monkeypatch, proofs,
):
    controller, events, written = _activation_controller(tmp_path, monkeypatch, proofs)
    result = controller.activate()
    assert events == [
        "key_fidelity", "activation-proof.json", "self-hosted-dev-active.json", "publish",
    ]
    receipt = json.loads(written["activation-proof.json"])
    assert receipt["locator_published"] is False
    assert receipt["ui_interactive_callback_verified"] is False
    assert json.loads(written["self-hosted-dev-active.json"])["source_sha"] == SHA
    assert result["usable"] is False
    assert result["ui_interactive_callback_verified"] is False


def test_key_failure_never_creates_the_activation_marker(tmp_path, monkeypatch, proofs):
    controller, events, written = _activation_controller(
        tmp_path, monkeypatch, proofs, fail_key=True,
    )
    with pytest.raises(candidate.Error, match="pinned_locator_identity_missing"):
        controller.activate()
    assert events == ["key_fidelity"]
    assert written == {}


def test_publication_failure_retains_the_new_marker_and_never_falls_back(
    tmp_path, monkeypatch, proofs,
):
    controller, events, written = _activation_controller(
        tmp_path, monkeypatch, proofs, fail_publish=True,
    )
    with pytest.raises(candidate.Error, match="locator_publication_failed"):
        controller.activate()
    assert events[-2:] == ["self-hosted-dev-active.json", "publish"]
    assert set(written) == {"activation-proof.json", "self-hosted-dev-active.json"}
    assert json.loads(written["self-hosted-dev-active.json"])["project"] == "reqsys-dev-selfhosted"
