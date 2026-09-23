import json

import pytest

from scripts import pc24x7_worker_pool_reconcile as reconcile


def _container(
    source: str,
    *,
    created: str,
    running: bool = False,
    canonical_binding: bool = True,
    compose_file: str = reconcile.COMPOSE_FILE,
) -> dict:
    host_bindings = []
    runtime_bindings = []
    if canonical_binding:
        host_bindings = [{"HostIp": reconcile.HOST_IP, "HostPort": reconcile.HOST_PORT}]
        runtime_bindings = [{"HostIp": reconcile.HOST_IP, "HostPort": reconcile.HOST_PORT}]
    return {
        "Created": created,
        "Config": {
            "Labels": {
                "com.docker.compose.service": reconcile.SERVICE,
                "com.docker.compose.project.config_files": f"C:/dev/reqsys/{compose_file}",
            }
        },
        "HostConfig": {"PortBindings": {reconcile.CONTAINER_PORT: host_bindings}},
        "State": {"Running": running},
        "NetworkSettings": {"Ports": {reconcile.CONTAINER_PORT: runtime_bindings}},
        "Mounts": [
            {
                "Type": "bind",
                "Source": source,
                "Destination": reconcile.TOKEN_DESTINATION,
            }
        ],
    }


def test_discovers_latest_canonical_token_source_from_container_history(
    tmp_path, monkeypatch
) -> None:
    old = tmp_path / "old.token"
    latest = tmp_path / "latest.token"
    old.write_text("old", encoding="utf-8")
    latest.write_text("latest", encoding="utf-8")
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(
        reconcile, "_service_container_ids", lambda *, all_containers: ["old", "new"]
    )
    monkeypatch.setattr(
        reconcile,
        "_inspect",
        lambda _ids: [
            _container(str(old), created="2026-09-20T10:00:00Z"),
            _container(str(latest), created="2026-09-22T10:00:00Z"),
        ],
    )

    resolved, method, created = reconcile.discover_token_source()

    assert resolved == latest
    assert method == "latest_ranked_canonical_docker_mount_history"
    assert created is False


def test_ignores_noncanonical_compose_and_binding_history(tmp_path, monkeypatch) -> None:
    expected = tmp_path / "expected.token"
    ignored = tmp_path / "ignored.token"
    expected.write_text("expected", encoding="utf-8")
    ignored.write_text("ignored", encoding="utf-8")
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(
        reconcile,
        "_service_container_ids",
        lambda *, all_containers: ["one", "two", "three"],
    )
    monkeypatch.setattr(
        reconcile,
        "_inspect",
        lambda _ids: [
            _container(str(expected), created="2026-09-20T10:00:00Z"),
            _container(
                str(ignored),
                created="2026-09-22T10:00:00Z",
                canonical_binding=False,
            ),
            _container(
                str(ignored),
                created="2026-09-23T10:00:00Z",
                compose_file="other-compose.yml",
            ),
        ],
    )

    resolved, _method, created = reconcile.discover_token_source()

    assert resolved == expected
    assert created is False


def test_latest_timestamp_with_different_sources_fails_closed(
    tmp_path, monkeypatch
) -> None:
    first = tmp_path / "first.token"
    second = tmp_path / "second.token"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(
        reconcile, "_service_container_ids", lambda *, all_containers: ["one", "two"]
    )
    monkeypatch.setattr(
        reconcile,
        "_inspect",
        lambda _ids: [
            _container(str(first), created="2026-09-22T10:00:00Z"),
            _container(str(second), created="2026-09-22T10:00:00Z"),
        ],
    )

    with pytest.raises(
        reconcile.ReconcileError, match="worker_pool_latest_token_source_ambiguous"
    ):
        reconcile.discover_token_source()


def test_created_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(
        reconcile.ReconcileError, match="worker_pool_container_created_invalid"
    ):
        reconcile._created_at({"Created": "2026-09-22T10:00:00"})


def test_canonical_endpoint_requires_exact_loopback_binding(monkeypatch) -> None:
    monkeypatch.setattr(
        reconcile, "_service_container_ids", lambda *, all_containers: ["old", "active"]
    )
    monkeypatch.setattr(
        reconcile,
        "_inspect",
        lambda _ids: [
            _container(
                "ignored",
                created="2026-09-20T10:00:00Z",
                running=True,
                canonical_binding=False,
            ),
            _container(
                "ignored",
                created="2026-09-22T10:00:00Z",
                running=True,
                canonical_binding=True,
            ),
        ],
    )

    endpoints = reconcile._canonical_endpoint_containers()

    assert len(endpoints) == 1


def test_evidence_does_not_require_secret_or_token_path(tmp_path) -> None:
    evidence = tmp_path / "evidence.json"
    payload = {
        "result": "WORKER_POOL_RUNTIME_RECONCILED",
        "token_source_method": "latest_ranked_canonical_docker_mount_history",
        "token_content_read": False,
    }

    reconcile.write_evidence(evidence, payload)
    written = json.loads(evidence.read_text(encoding="utf-8"))

    assert written["token_content_read"] is False
    assert "token_source" not in written


def test_falls_back_to_latest_existing_service_mount_when_historical_metadata_is_absent(
    tmp_path, monkeypatch
) -> None:
    old = tmp_path / "old.token"
    newest = tmp_path / "newest.token"
    old.write_text("old", encoding="utf-8")
    newest.write_text("newest", encoding="utf-8")
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(
        reconcile,
        "_service_container_ids",
        lambda *, all_containers: ["old", "new"],
    )

    def plain(source: str, created: str) -> dict:
        container = _container(
            source,
            created=created,
            canonical_binding=False,
            compose_file="legacy-compose.yml",
        )
        container["Config"]["Labels"].pop("com.docker.compose.project.config_files")
        return container

    monkeypatch.setattr(
        reconcile,
        "_inspect",
        lambda _ids: [
            plain(str(old), "2026-09-20T10:00:00Z"),
            plain(str(newest), "2026-09-22T10:00:00Z"),
        ],
    )

    resolved, method, created = reconcile.discover_token_source()

    assert resolved == newest
    assert method == "latest_ranked_canonical_docker_mount_history"
    assert created is False


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("/run/desktop/mnt/host/c/secure/worker.token", r"C:\\secure\\worker.token"),
        ("/host_mnt/d/reqsys/token", r"D:\\reqsys\\token"),
        ("/mnt/e/runtime/token", r"E:\\runtime\\token"),
    ],
)
def test_translates_docker_desktop_host_paths(source: str, expected: str) -> None:
    candidates = [str(path) for path in reconcile._host_path_candidates(source)]

    assert expected in candidates


def test_provisions_local_dev_token_when_no_history_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(reconcile, "_service_container_ids", lambda *, all_containers: [])
    monkeypatch.setattr(reconcile, "_inspect", lambda _ids: [])

    resolved, method, created = reconcile.discover_token_source()

    assert resolved.is_file()
    assert method == "local_dev_generated"
    assert created is True
    assert resolved.stat().st_size >= 32


def test_local_dev_token_bootstrap_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("CODEX_WORKER_POOL_API_TOKEN_FILE_HOST", raising=False)
    monkeypatch.setattr(reconcile, "_service_container_ids", lambda *, all_containers: [])
    monkeypatch.setattr(reconcile, "_inspect", lambda _ids: [])

    first, _method, first_created = reconcile.discover_token_source()
    before = first.read_bytes()
    second, _method2, second_created = reconcile.discover_token_source()

    assert second == first
    assert first_created is True
    assert second_created is False
    assert second.read_bytes() == before
