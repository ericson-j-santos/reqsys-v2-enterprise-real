"""Contratos de coleta física local: sem shell, credenciais, alterações ou falso HML."""
import json
from unittest.mock import Mock, patch


from scripts import desktop_sql_hml_host_inventory_dev as subject


def services():
    return {
        "status": "measured",
        "services": [
            {"name_hash": subject.fingerprint("com.docker.service"),
             "kind": "docker", "state": "running"},
        ],
        "sql_engine_running": 0,
    }


def response_for(args):
    assert args[0] == r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    assert args[1] == "--host"
    assert args[2] in [x[1] for x in subject.LOCAL_ENGINES]
    assert args[3:] in [
        ["version", "--format", "{{json .Server}}"],
        ["ps", "--all", "--format", "{{json .}}"],
        ["volume", "ls", "--format", "{{json .}}"],
        ["network", "ls", "--format", "{{json .}}"],
    ]
    if args[3] == "version":
        return json.dumps({"Version": "28.3.0", "Os": "linux"})
    if args[3] == "ps":
        return "\n".join((
            json.dumps({
                "Names": "worker-1", "State": "running",
                "Image": "other.internal/worker:stable",
                "Ports": "0.0.0.0:8210->8000/tcp, :::8210->8000/tcp",
            }),
            json.dumps({
                "Names": "sql-old", "State": "exited",
                "Image": "mcr.microsoft.com/mssql/server:2025-latest",
                "Ports": "",
            }),
        ))
    if args[3] == "volume":
        return json.dumps({"Name": "sensitive-volume-name", "Driver": "local"})
    if args[3] == "network":
        return json.dumps({"Name": "private-net", "Driver": "bridge", "Internal": "true"})
    raise AssertionError(args)


def test_positive_local_engine_and_sql_services_idempotent_and_sanitized():
    runner = Mock(side_effect=lambda argv, env: response_for(argv))
    first = subject.collect(
        platform="nt", cli_path=r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
        docker_runner=runner, service_reader=services,
    )
    second = subject.collect(
        platform="nt", cli_path=r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
        docker_runner=runner, service_reader=services,
    )
    assert first == second
    assert first["status"] == "measured"
    docker = first["docker"]
    assert docker["engine_verified"] is True
    assert docker["engine_type"] == "linux"
    assert docker["engine_version"] == "28.3.0"
    assert docker["local_endpoint"] == "desktop-linux"
    assert docker["published_tcp_ports"] == [8210]
    assert [x["state"] for x in docker["containers"]] == ["running", "exited"]
    assert [x["sqlserver_image"] for x in docker["containers"]] == [False, True]
    assert docker["volumes"][0]["driver"] == "local"
    assert docker["networks"][0]["internal"] is True
    for unsafe in ("worker-1", "sensitive-volume-name", "private-net",
                   "other.internal", "sql-old", "MSSQL_SA_PASSWORD"):
        assert unsafe not in json.dumps(first)
    assert first["hml_provisioning_authorized"] is False
    assert first["production_touched"] is False
    assert first["secrets_read"] is False
    assert runner.call_count == 8


def test_env_disallows_remote_docker_context_and_credentials():
    with patch.dict(subject.os.environ, {
        "DOCKER_HOST": "tcp://evil:2376",
        "DOCKER_CONTEXT": "remote",
        "DOCKER_TLS_VERIFY": "1",
        "DOCKER_CERT_PATH": r"C:\secret",
        "RUNNER_TEMP": r"C:\runner\_temp",
    }):
        env = subject._docker_env()
    for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY",
                "DOCKER_CERT_PATH"):
        assert key not in env
    assert env["DOCKER_CONFIG"].startswith(r"C:\runner\_temp")
    assert env["DOCKER_CONFIG"].endswith("_reqsys_sql_readonly_docker_config_absent")


def test_docker_engine_offline_is_not_verification():
    requests = []
    def engine_offline(args, env):
        requests.append(args)
        raise subject.InventoryError("docker_command_unavailable")
    result = subject.collect(
        platform="nt", cli_path=r"C:\Program Files\Docker\Docker\resources\bin\docker.exe", docker_runner=engine_offline,
        service_reader=services,
    )
    assert result["status"] == "partial"
    assert result["docker"]["engine_verified"] is False
    assert result["docker"]["reason"] == "local_engine_not_verified"
    assert len(requests) == len(subject.LOCAL_ENGINES)
    assert all("npipe:" in x[2] for x in requests)


def test_absent_docker_binary_and_windows_service_are_distinct():
    result = subject.collect(
        platform="nt", cli_path="", service_reader=services,
        docker_runner=Mock(side_effect=AssertionError("cannot call docker")),
    )
    assert result["status"] == "partial"
    assert result["docker"]["cli_present"] is False
    assert result["docker"]["reason"] == "docker_cli_missing"
    assert result["windows_services"]["status"] == "measured"


def test_windows_engine_not_sql_linux_ready():
    def windows_runner(args, env):
        if args[3] == "version":
            return '{"Version":"28.3.0","Os":"windows"}'
        return ""
    result = subject.collect(
        platform="nt", cli_path=r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
        service_reader=services, docker_runner=windows_runner,
    )
    assert result["docker"]["engine_verified"] is True
    assert result["docker"]["engine_type"] == "windows"
    assert result["hml_provisioning_authorized"] is False


def test_no_nonwindows_physical_probe_even_if_runner_supplied():
    runner = Mock()
    result = subject.collect(
        platform="posix", cli_path=r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
        docker_runner=runner, service_reader=Mock(),
    )
    assert result["reason"] == "windows_required"
    assert result["status"] == "unavailable"
    runner.assert_not_called()


def test_reject_nonexe_wrapper_to_avoid_shell():
    runner = Mock()
    result = subject.collect(
        platform="nt", cli_path=r"C:\docker.cmd",
        docker_runner=runner, service_reader=services,
    )
    assert result["docker"]["engine_verified"] is False
    assert result["docker"]["reason"] == "docker_cli_untrusted"
    runner.assert_not_called()


def test_malformed_or_excessive_docker_metadata_fail_closed():
    for response in ("not json", "\n".join('{"Name":"v"}' for _ in range(65))):
        def bad_runner(args, env):
            if args[3] == "version":
                return '{"Version":"28.3.0","Os":"linux"}'
            if args[3] == "ps":
                return response
            return ""
        result = subject.collect(
            platform="nt", cli_path=r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
            docker_runner=bad_runner, service_reader=services,
        )
        assert result["docker"]["status"] == "partial"
        assert result["docker"]["engine_verified"] is True
        assert result["docker"]["reason"] in ("docker_metadata_invalid", "docker_list_limit")
        assert result["hml_provisioning_authorized"] is False


def test_secrets_in_docker_errors_and_scm_exception_not_exposed():
    def unsafe(args, env):
        raise RuntimeError("secret=really-unsafe")
    def unsafe_service():
        raise RuntimeError("password=unsafe-scm")
    result = subject.collect(
        platform="nt", cli_path=r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
        docker_runner=unsafe, service_reader=unsafe_service,
    )
    data = json.dumps(result)
    assert "really-unsafe" not in data
    assert "unsafe-scm" not in data
    assert result["status"] == "unavailable"
    assert result["windows_services"]["status"] == "unavailable"
    assert result["hml_provisioning_authorized"] is False


def test_port_numbers_bounded_and_deduplicated():
    assert subject._published_tcp_ports(
        "0.0.0.0:8210->1433/tcp, :::8210->1433/tcp, 1.1.1.1:65536->1433/tcp"
    ) == [8210]
    assert subject._published_tcp_ports("not-a-port") == []

def test_untrusted_docker_cli_attests_without_executing_or_leaking_paths():
    import io
    from types import SimpleNamespace

    path = r"C:\Users\Example\Temp\docker.exe"
    binary = b"MZ" + b"test" * 1024
    stat = SimpleNamespace(st_size=len(binary), st_file_attributes=0)
    runner = Mock(side_effect=AssertionError("untrusted binary was launched"))
    with (
        patch.object(subject.os, "lstat", return_value=stat),
        patch("builtins.open", side_effect=lambda *_: io.BytesIO(binary)),
        patch.object(subject, "_win_authenticode_status", return_value="valid"),
    ):
        first = subject.collect(
            platform="nt", cli_path=path, docker_runner=runner, service_reader=services,
        )
        second = subject.collect(
            platform="nt", cli_path=path, docker_runner=runner, service_reader=services,
        )
    assert first == second
    assert first["status"] == "partial"
    assert first["docker"]["reason"] == "docker_cli_untrusted"
    attestation = first["docker"]["provenance"]
    assert attestation["status"] == "observed"
    assert attestation["authenticode_status"] == "valid"
    assert attestation["file_sha256"] == subject.hashlib.sha256(binary).hexdigest()
    assert attestation["size_bytes"] == len(binary)
    assert attestation["location_class"] == "user_profile"
    assert attestation["executable_launched"] is False
    assert path not in json.dumps(first)
    assert first["hml_provisioning_authorized"] is False
    runner.assert_not_called()


def test_untrusted_cli_attestation_rejects_remote_and_nonexe_without_file_access():
    probe = Mock(side_effect=AssertionError("no read"))
    with patch.object(subject.os, "lstat", probe):
        remote = subject._untrusted_cli_provenance(r"\\server\share\docker.exe")
        wrapper = subject._untrusted_cli_provenance(r"C:\Temp\docker.cmd")
    assert remote["reason"] == "local_exe_required"
    assert wrapper["reason"] == "local_exe_required"
    assert remote["file_sha256"] is None
    assert wrapper["authenticode_status"] == "unavailable"
    probe.assert_not_called()


def test_reparse_point_attestation_fails_closed_without_signature_call():
    from types import SimpleNamespace

    validator = Mock(side_effect=AssertionError("no signature check"))
    with (
        patch.object(
            subject.os, "lstat",
            return_value=SimpleNamespace(st_size=4096, st_file_attributes=0x400),
        ),
        patch.object(subject, "_win_authenticode_status", validator),
    ):
        result = subject._untrusted_cli_provenance(r"C:\Temp\docker.exe")
    assert result["reason"] == "reparse_point_blocked"
    assert result["status"] == "unavailable"
    assert result["file_sha256"] is None
    validator.assert_not_called()


def test_untrusted_cli_read_failure_sanitizes_secrets_and_never_runs():
    runner = Mock(side_effect=AssertionError("CLI cannot run"))
    with patch.object(subject.os, "lstat", side_effect=PermissionError("token=NEVER-PRINT")):
        result = subject.collect(
            platform="nt", cli_path=r"C:\Temp\docker.exe",
            docker_runner=runner, service_reader=services,
        )
    assert result["docker"]["reason"] == "docker_cli_untrusted"
    assert result["docker"]["provenance"]["reason"] == "file_read_unavailable"
    assert "NEVER-PRINT" not in json.dumps(result)
    assert result["hml_provisioning_authorized"] is False
    runner.assert_not_called()


def test_untrusted_cli_valid_signature_does_not_become_an_allowlist():
    import io
    from types import SimpleNamespace

    binary = b"MZ" + b"x" * 2048
    runner = Mock(side_effect=AssertionError("no execution after valid signature"))
    with (
        patch.object(subject.os, "lstat", return_value=SimpleNamespace(
            st_size=len(binary), st_file_attributes=0,
        )),
        patch("builtins.open", side_effect=lambda *_: io.BytesIO(binary)),
        patch.object(subject, "_win_authenticode_status", return_value="valid"),
    ):
        result = subject.collect(
            platform="nt", cli_path=r"C:\Windows\Temp\docker.exe",
            docker_runner=runner, service_reader=services,
        )
    assert result["docker"]["engine_verified"] is False
    assert result["docker"]["reason"] == "docker_cli_untrusted"
    assert result["docker"]["provenance"]["authenticode_status"] == "valid"
    assert result["hml_provisioning_authorized"] is False
    runner.assert_not_called()

def test_signed_official_cli_replaces_untrusted_path_without_running_wrapper():
    from types import SimpleNamespace

    official = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    untrusted = r"C:\Users\Example\docker.exe"
    runner = Mock(side_effect=lambda argv, env: response_for(argv))
    with (
        patch.object(
            subject.os, "lstat",
            return_value=SimpleNamespace(st_size=40_000_000, st_file_attributes=0),
        ),
        patch.object(subject.os.path, "isfile", side_effect=lambda p: p == official),
        patch.object(subject, "_win_authenticode_status", return_value="valid") as cert,
        patch.object(
            subject, "_untrusted_cli_provenance",
            return_value={"status": "observed", "executable_launched": False},
        ) as probe,
    ):
        first = subject.collect(
            platform="nt", cli_path=untrusted, docker_runner=runner,
            service_reader=services,
        )
        second = subject.collect(
            platform="nt", cli_path=untrusted, docker_runner=runner,
            service_reader=services,
        )
    assert first == second
    assert first["docker"]["cli_selection"] == "signed_official_path"
    assert first["docker"]["engine_verified"] is True
    assert first["docker"]["engine_type"] == "linux"
    assert first["hml_provisioning_authorized"] is False
    assert runner.call_count == 8
    assert cert.call_count == 2
    assert probe.call_count == 2
    assert all(call.args[0][0] == official for call in runner.call_args_list)


def test_unsigned_official_cli_does_not_override_untrusted_path():
    from types import SimpleNamespace

    runner = Mock(side_effect=AssertionError("must not execute untrusted or unsigned CLI"))
    with (
        patch.object(subject.os, "lstat", return_value=SimpleNamespace(
            st_size=40_000_000, st_file_attributes=0,
        )),
        patch.object(subject.os.path, "isfile", return_value=True),
        patch.object(subject, "_win_authenticode_status", return_value="not_trusted"),
        patch.object(subject, "_untrusted_cli_provenance", return_value={"status": "unavailable"}),
    ):
        result = subject.collect(
            platform="nt", cli_path=r"C:\Users\Example\docker.exe",
            docker_runner=runner, service_reader=services,
        )
    assert result["docker"]["engine_verified"] is False
    assert result["docker"]["reason"] == "docker_cli_untrusted"
    assert "cli_selection" not in result["docker"]
    runner.assert_not_called()


def test_reparse_official_cli_is_rejected_without_signature_verification():
    from types import SimpleNamespace

    runner = Mock(side_effect=AssertionError("no execution"))
    signed = Mock(side_effect=AssertionError("reparse cannot be verified"))
    with (
        patch.object(subject.os, "lstat", return_value=SimpleNamespace(
            st_size=40_000_000, st_file_attributes=0x400,
        )),
        patch.object(subject.os.path, "isfile", return_value=True),
        patch.object(subject, "_win_authenticode_status", signed),
        patch.object(subject, "_untrusted_cli_provenance", return_value={"status": "unavailable"}),
    ):
        result = subject.collect(
            platform="nt", cli_path=r"C:\Users\Example\docker.exe",
            docker_runner=runner, service_reader=services,
        )
    assert result["docker"]["reason"] == "docker_cli_untrusted"
    assert result["hml_provisioning_authorized"] is False
    signed.assert_not_called()
    runner.assert_not_called()


def test_missing_official_installation_remains_closed_even_when_path_cli_signed():
    runner = Mock(side_effect=AssertionError("no execution"))
    with (
        patch.object(subject.os, "lstat", side_effect=FileNotFoundError("not installed")),
        patch.object(subject, "_untrusted_cli_provenance", return_value={
            "status": "observed", "authenticode_status": "valid",
        }),
    ):
        result = subject.collect(
            platform="nt", cli_path=r"C:\Users\Example\docker.exe",
            docker_runner=runner, service_reader=services,
        )
    assert result["docker"]["reason"] == "docker_cli_untrusted"
    assert result["docker"]["provenance"]["authenticode_status"] == "valid"
    assert result["docker"]["engine_verified"] is False
    runner.assert_not_called()
