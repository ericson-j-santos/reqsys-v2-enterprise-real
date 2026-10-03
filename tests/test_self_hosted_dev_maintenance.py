from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import self_hosted_dev_maintenance as maintenance

ROOT = Path(__file__).resolve().parents[1]
SHA = "1" * 40


def _marker():
    return {
        "schema_version": "1.0.0", "host": maintenance.HOST,
        "environment": "dev", "project": maintenance.PROJECT,
        "instance": maintenance.INSTANCE, "source_sha": SHA,
    }


def _write_marker(tmp_path, monkeypatch, payload=None):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    path = tmp_path / "ReqSys" / "RuntimeSupervisor" / maintenance.MARKER_NAME
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload if payload is not None else _marker()), encoding="utf-8")
    return path


def _load(filename):
    name = "portable_guard_test_" + filename.removesuffix(".py")
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _forbidden(*_args, **_kwargs):
    pytest.fail("Legacy runtime or mutation must not run after a marker is observed")


def _ready():
    return {
        "runtime_provider": "self_hosted_dev", "maintenance_verified": True,
        "maintenance_read_only": True, "usable": False,
        "authenticated_flow_verified": False, "public_ingress_verified": False,
        "expected_sha": SHA, "host": maintenance.HOST, "project": maintenance.PROJECT,
        "legacy_runtime_touched": False,
    }


def test_absent_marker_preserves_legacy_selection_without_touching_docker(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(maintenance, "_inspect", _forbidden)
    assert maintenance.verify_if_active() is None
    assert not (tmp_path / "ReqSys").exists()


@pytest.mark.parametrize("key,value", [
    ("environment", "production"), ("host", "NOTERI"),
    ("project", "reqsys-live"), ("instance", "other"),
    ("source_sha", "main"), ("schema_version", "2"),
])
def test_invalid_present_marker_blocks_legacy_fallback(tmp_path, monkeypatch, key, value):
    payload = _marker()
    payload[key] = value
    _write_marker(tmp_path, monkeypatch, payload)
    monkeypatch.setattr(maintenance, "_inspect", _forbidden)
    with pytest.raises(maintenance.PortableRuntimeError, match="marker_identity_invalid"):
        maintenance.verify_if_active()


def test_marker_cannot_inject_a_path_target_or_command(tmp_path, monkeypatch):
    payload = {**_marker(), "target": "http://other.invalid"}
    _write_marker(tmp_path, monkeypatch, payload)
    with pytest.raises(maintenance.PortableRuntimeError, match="marker_schema_invalid"):
        maintenance.verify_if_active()


def test_invalid_json_marker_does_not_fall_back(tmp_path, monkeypatch):
    path = _write_marker(tmp_path, monkeypatch)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(maintenance.PortableRuntimeError, match="marker_invalid_json"):
        maintenance.verify_if_active()


def test_dangling_symlink_marker_does_not_mean_legacy_mode(tmp_path, monkeypatch):
    path = _write_marker(tmp_path, monkeypatch)
    path.unlink()
    try:
        path.symlink_to(tmp_path / "missing-target")
    except OSError:
        pytest.skip("Symlink creation is unavailable for this test user")
    with pytest.raises(maintenance.PortableRuntimeError, match="marker_reparse_blocked"):
        maintenance.verify_if_active()


def test_expected_source_sha_mismatch_blocks_before_docker(tmp_path, monkeypatch):
    _write_marker(tmp_path, monkeypatch)
    monkeypatch.setattr(maintenance, "_require_host", lambda: None)
    monkeypatch.setattr(maintenance, "_inspect", _forbidden)
    with pytest.raises(maintenance.PortableRuntimeError, match="expected_sha_mismatch"):
        maintenance.verify_if_active("2" * 40)


def _container(service="api"):
    return {
        "id": "a" * 64, "name": f"/{maintenance.PROJECT}-{service}-1",
        "labels": {
            "com.docker.compose.project": maintenance.PROJECT,
            "com.docker.compose.service": service,
            "io.reqsys.selfhost.instance": maintenance.INSTANCE,
        },
        "state": {"Running": True, "Health": {"Status": "healthy"}},
    }


@pytest.mark.parametrize("case", ["wrong_project", "wrong_instance", "wrong_service", "unhealthy", "not_running"])
def test_container_ownership_and_health_are_required(monkeypatch, case):
    payload = _container()
    if case == "wrong_project":
        payload["labels"]["com.docker.compose.project"] = "reqsys-live"
    elif case == "wrong_instance":
        payload["labels"]["io.reqsys.selfhost.instance"] = "other"
    elif case == "wrong_service":
        payload["labels"]["com.docker.compose.service"] = "frontend"
    elif case == "unhealthy":
        payload["state"]["Health"]["Status"] = "unhealthy"
    else:
        payload["state"]["Running"] = False

    def fake_run(argv, **kwargs):
        assert argv == [
            "docker", "inspect", "--format", maintenance.INSPECT_FORMAT,
            "reqsys-dev-selfhosted-api-1",
        ]
        assert kwargs["shell"] is False
        assert kwargs["timeout"] <= 12
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload))

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(maintenance.PortableRuntimeError):
        maintenance._inspect("api", maintenance.time.monotonic() + 30)


def _payload(endpoint, published_sha=SHA):
    data = {"service": "reqsys-api"}
    if endpoint == "/api/health":
        data.update(status="ok", database={"status": "ok", "detail": "ok"})
    elif endpoint == "/api/runtime/build-info":
        data.update(build_sha=published_sha, environment="desenvolvimento")
    else:
        readiness = endpoint.endswith("/readiness")
        data.update(
            status="ready" if readiness else "ok",
            check="readiness" if readiness else "health",
            schema_version="1.1.0", environment="desenvolvimento",
        )
    return {"success": True, "errors": [], "data": data}


def _probes(monkeypatch, published_sha=SHA):
    monkeypatch.setattr(maintenance, "_require_host", lambda: None)
    monkeypatch.setattr(maintenance, "_inspect", lambda service, deadline: {"service": service, "healthy": True})

    def fake_get(path, deadline, json_body=False):
        if path == "/@vite/client":
            return 404, None
        if path == "/task-console":
            return 200, True
        if path == "/api/runtime/build-info":
            return 200, _payload(path, published_sha)
        return 200, _payload(path)

    monkeypatch.setattr(maintenance, "_get", fake_get)


def test_live_api_sha_must_match_marker(tmp_path, monkeypatch):
    _write_marker(tmp_path, monkeypatch)
    _probes(monkeypatch, published_sha="2" * 40)
    with pytest.raises(maintenance.PortableRuntimeError, match="build_sha_mismatch"):
        maintenance.verify_if_active(SHA)


def test_valid_mode_is_read_only_and_cannot_claim_login_or_usability(tmp_path, monkeypatch):
    path = _write_marker(tmp_path, monkeypatch)
    before = path.read_bytes()
    _probes(monkeypatch)
    result = maintenance.verify_if_active(SHA)
    assert result["maintenance_verified"] is True
    assert result["maintenance_read_only"] is True
    assert result["expected_sha"] == SHA
    assert result["usable"] is False
    assert result["authenticated_flow_verified"] is False
    assert result["public_ingress_verified"] is False
    assert result["locator_published"] is False
    assert path.read_bytes() == before


@pytest.mark.parametrize("filename,blocked_name", [
    ("pc24x7_dev_runtime_supervisor.py", "ensure_containers"),
    ("pc24x7_public_dev_tunnel.py", "reconcile_one"),
    ("pc24x7_dev_locator_publisher.py", "ensure_identity"),
])
def test_public_entrypoints_do_not_touch_legacy_runtime_with_valid_marker(
    monkeypatch, filename, blocked_name,
):
    if filename == "pc24x7_dev_locator_publisher.py":
        pytest.importorskip("cryptography")
    module = _load(filename)
    monkeypatch.setattr(module.portable_dev, "control_if_active", lambda *args, **kwargs: _ready())
    monkeypatch.setattr(module, blocked_name, _forbidden)
    monkeypatch.setattr(sys, "argv", [filename])
    assert module.main() == 0


@pytest.mark.parametrize("filename", [
    "pc24x7_dev_runtime_supervisor.py",
    "pc24x7_public_dev_tunnel.py",
    "pc24x7_dev_locator_publisher.py",
])
def test_invalid_marker_cli_fails_without_discovering_legacy_resources(monkeypatch, filename):
    if filename == "pc24x7_dev_locator_publisher.py":
        pytest.importorskip("cryptography")
    module = _load(filename)

    def invalid(*args, **kwargs):
        raise maintenance.PortableRuntimeError("portable_runtime_marker_identity_invalid")

    monkeypatch.setattr(module.portable_dev, "control_if_active", invalid)
    monkeypatch.setattr(sys, "argv", [filename])
    assert module.main() == 2


def test_study_mode_guard_runs_before_git_or_legacy_discovery(tmp_path, monkeypatch):
    module = _load("noteri_study_mode_dev_reconcile.py")
    monkeypatch.setattr(module, "require_host", lambda: None)
    monkeypatch.setattr(module.portable_dev, "verify_if_active", lambda *args: _ready())
    monkeypatch.setattr(module, "git_head", _forbidden)
    monkeypatch.setattr(module, "discover_runtime", _forbidden)
    result = module.execute(SimpleNamespace(
        repo_root=tmp_path, expected_sha=SHA, confirm=module.CONFIRM,
    ))
    assert result["ok"] is True
    assert result["maintenance_verified"] is True
    assert result["legacy_study_mode_e2e_executed"] is False
    assert result["control_plane_bridge"] is False


def test_public_reconciler_guard_runs_before_credentials_and_legacy_discovery(tmp_path, monkeypatch):
    module = _load("reconcile_pc24x7_public_dev_runtime.py")
    monkeypatch.setattr(module.portable_dev, "verify_if_active", lambda *args: _ready())
    monkeypatch.setattr(module, "_discover_runtime", _forbidden)
    monkeypatch.setattr(module, "_recreate_public_stack", _forbidden)
    result = module.execute(SimpleNamespace(
        confirm=module.CONFIRMATION, environment="dev", expected_sha=SHA,
        correlation_id="portable-contract-test", evidence_file=tmp_path / "evidence.json",
        vault_name="", expected_tenant_id="",
    ))
    assert result["maintenance_verified"] is True
    assert result["usable"] is False
    assert result["credentials_reused"] is False


def test_persistent_installer_includes_the_guard_module():
    module = _load("pc24x7_dev_runtime_supervisor_install.py")
    assert "self_hosted_dev_maintenance.py" in module.SOURCE_SCRIPTS


@pytest.mark.parametrize("filename,discovery", [
    ("noteri_study_mode_dev_reconcile.py", "discover_runtime"),
    ("reconcile_pc24x7_public_dev_runtime.py", "_discover_runtime"),
])
def test_invalid_marker_reconciler_blocks_before_legacy_mutation(tmp_path, monkeypatch, filename, discovery):
    module = _load(filename)
    if filename == "noteri_study_mode_dev_reconcile.py":
        monkeypatch.setattr(module, "require_host", lambda: None)
        args = SimpleNamespace(repo_root=tmp_path, expected_sha=SHA, confirm=module.CONFIRM)
    else:
        args = SimpleNamespace(
            expected_sha=SHA, confirm=module.CONFIRMATION, environment="dev",
            vault_name="", expected_tenant_id="",
        )

    def invalid(*args):
        raise maintenance.PortableRuntimeError("portable_runtime_marker_identity_invalid")

    monkeypatch.setattr(module.portable_dev, "verify_if_active", invalid)
    monkeypatch.setattr(module, discovery, _forbidden)
    with pytest.raises(module.ReconcileError, match="portable_runtime_marker_identity_invalid"):
        module.execute(args)


def test_workflow_distinguishes_read_only_maintenance_from_legacy_e2e():
    raw = (ROOT / ".github" / "workflows" / "noteri-study-mode-dev-reconcile.yml").read_text(encoding="utf-8")
    portable, legacy = raw.split("if ($e.runtime_provider -eq 'self_hosted_dev') {", 1)[1].split("} else {", 1)
    assert "portable_maintenance_not_verified" in portable
    assert "portable_maintenance_cannot_claim_usable" in portable
    assert "portable_maintenance_cannot_claim_login" in portable
    assert "api_readback_missing" not in portable
    assert "api_readback_missing" in legacy
    assert "ui_estudo_not_observed" in legacy


def test_duplicate_marker_keys_are_rejected_even_with_identical_values(tmp_path, monkeypatch):
    path = _write_marker(tmp_path, monkeypatch)
    raw = json.dumps(_marker())
    path.write_text(raw[:-1] + ', "source_sha": "' + SHA + '"}', encoding="utf-8")
    with pytest.raises(maintenance.PortableRuntimeError, match="json_duplicate_key"):
        maintenance.verify_if_active()


def test_every_existing_marker_ancestor_is_checked_for_reparse(tmp_path, monkeypatch):
    _write_marker(tmp_path, monkeypatch)
    original = Path.lstat

    def fake_lstat(path):
        if path == tmp_path.parent:
            return SimpleNamespace(st_mode=maintenance.stat.S_IFDIR, st_file_attributes=0x400)
        return original(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(maintenance.PortableRuntimeError, match="marker_reparse_blocked"):
        maintenance.verify_if_active()


@pytest.mark.parametrize("service", ["redis", "frontend", "gateway", "caddy"])
def test_running_services_without_healthcheck_are_not_reported_healthy(monkeypatch, service):
    payload = _container(service)
    payload["state"].pop("Health")
    monkeypatch.setattr(
        subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload)),
    )
    observed = maintenance._inspect(service, maintenance.time.monotonic() + 30)
    assert observed["running"] is True
    assert observed["health_configured"] is False
    assert observed["healthy"] is None


@pytest.mark.parametrize("service", ["api", "db"])
def test_healthcheck_is_required_for_database_and_api(monkeypatch, service):
    payload = _container(service)
    payload["state"].pop("Health")
    monkeypatch.setattr(
        subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload)),
    )
    with pytest.raises(maintenance.PortableRuntimeError, match="container_health_missing"):
        maintenance._inspect(service, maintenance.time.monotonic() + 30)


@pytest.mark.parametrize("endpoint,change", [
    ("/api/health", "degraded"),
    ("/api/health", "database_unavailable"),
    ("/api/runtime/health", "degraded"),
    ("/api/runtime/health", "healthy_false"),
    ("/api/runtime/health", "failed_dependency"),
    ("/api/runtime/readiness", "degraded"),
    ("/api/runtime/readiness", "ready_false"),
    ("/api/runtime/readiness", "invalid_schema"),
    ("/api/runtime/readiness", "production"),
    ("/api/runtime/readiness", "failed_envelope"),
    ("/api/runtime/readiness", "reported_errors"),
    ("/api/runtime/build-info", "wrong_service"),
])
def test_http_200_negative_json_cannot_be_a_ready_contract(
    tmp_path, monkeypatch, endpoint, change,
):
    _write_marker(tmp_path, monkeypatch)
    _probes(monkeypatch)
    original_probe = maintenance._get
    payload = _payload(endpoint)
    data = payload["data"]
    if change == "degraded":
        data["status"] = "degraded"
    elif change == "database_unavailable":
        data["database"]["status"] = "unavailable"
    elif change == "healthy_false":
        data["healthy"] = False
    elif change == "failed_dependency":
        data["checks"] = {"database": "ok", "redis": "unavailable"}
    elif change == "ready_false":
        data["ready"] = False
    elif change == "invalid_schema":
        data["schema_version"] = "unknown"
    elif change == "production":
        data["environment"] = "producao"
    elif change == "failed_envelope":
        payload["success"] = False
    elif change == "reported_errors":
        payload["errors"] = [{"code": "not_ready"}]
    else:
        data["service"] = "other-service"

    def negative_probe(path, deadline, json_body=False):
        if path == endpoint:
            return 200, payload
        return original_probe(path, deadline, json_body=json_body)

    monkeypatch.setattr(maintenance, "_get", negative_probe)
    with pytest.raises(maintenance.PortableRuntimeError):
        maintenance.verify_if_active(SHA)


def test_duplicate_keys_in_live_http_json_are_rejected(monkeypatch):
    raw = b'{"success":true,"errors":[],"data":{"status":"ready","ready":false,"ready":true}}'

    class Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, maximum):
            assert maximum == 524289
            return raw

    monkeypatch.setattr(maintenance._OPENER, "open", lambda *args, **kwargs: Response())
    with pytest.raises(maintenance.PortableRuntimeError, match="json_duplicate_key"):
        maintenance._get(
            "/api/runtime/readiness", maintenance.time.monotonic() + 30, json_body=True,
        )
