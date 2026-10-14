"""Fixed read-only DEV deploy check — issue #2546."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.deploy_check_receipt import PUBLIC_KEYS, ReceiptContext, build_receipt

ROOT = Path(__file__).resolve().parents[1]
GW = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
WF = ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml"
CHECK = ROOT / "scripts/dev_runtime_recovery.py"
PARSER = ROOT / "scripts/deploy_check_receipt.py"
COMMAND = "/reqsys run pc24x7-dev-deploy-check"
TASK_ID = "cwp-cdb85c31e3cc4e972f3094ab"


def _job():
    raw = WF.read_text(encoding="utf-8")
    return raw.split("\n  deploy-check:\n", 1)[1].split("\n  task-2547-read:", 1)[0]


def test_gateway_command_and_admission_are_fixed():
    raw = GW.read_text(encoding="utf-8")
    assert "github.event.issue.number == 1705" in raw
    assert "github.event.comment.user.login == 'ericson-j-santos'" in raw
    assert "github.event.comment.body == '" + COMMAND + "'" in raw
    assert "'" + COMMAND + "')" in raw
    assert "mode='deploy-check'" in raw
    assert "-f mode=deploy-check" in raw
    assert raw.count("steps.route.outputs.mode == 'deploy-check'") == 2
    assert "scripts/authorized_teams_e2e_admission.py" in raw
    assert "if: steps.teams_admission.outputs.admitted != 'false'" in raw
    assert "-f task_id=" not in raw and "-f worker_id=" not in raw


def test_physical_job_exercises_existing_dev_readonly_command():
    raw = WF.read_text(encoding="utf-8")
    assert raw.count("\n  deploy-check:\n") == 1
    assert "          - deploy-check\n" in raw
    block = _job()
    required = (
        "if: ${{ inputs.mode == 'deploy-check' }}",
        "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]",
        "SESSION_LAUNCH_OK",
        "--require-runner-version-preflight",
        "--expected-head",
        'Join-Path $env:TARGET_PATH "scripts\\dev_runtime_recovery.py"',
        '"python", $script, "deploy-check"',
        '"--expected-sha", $env:ANCHOR_SHA',
        "scripts\\deploy_check_receipt.py",
        TASK_ID,
    )
    for item in required:
        assert item in block
    for bad in ("docker compose up", "docker compose down", "requeue",
                "POST /v1/claims", "-f mode=prod"):
        assert bad not in block


def test_workflow_uses_real_sanitizing_parser_and_fails_closed():
    block = _job()
    expected = (
        'scripts\\deploy_check_receipt.py',
        '"--gateway-exit-code", [string]$gatewayExit',
        'scripts\\run_deploy_check_gateway_capture.ps1',
        'scripts\\private_process_capture.py',
        '"--gateway-stdout-file", $stdoutPath',
        '"--gateway-stderr-file", $stderrPath',
        '$sanitized = @(& "$env:REQSYS_PYTHON" $parser @parserArgs)',
        'Remove-Item -LiteralPath $privatePath -Force',
        'throw "DEPLOY_CHECK_BLOCKED:$($receipt.reason_code)"',
        'throw "DEPLOY_CHECK_EVIDENCE_MISSING"',
        'throw "DEPLOY_CHECK_EVIDENCE_INVALID"',
        'throw "DEPLOY_CHECK_SAFETY_INVALID"',
        '$e.database_result -ne "passed"',
        '$e.gateway_exit_code -ne 0',
        '$e.command_exit_code -ne 0',
        '$e.result_verified -ne $true',
        "if: always()",
    )
    for item in expected:
        assert item in block
    assert '[System.Text.UTF8Encoding]::new($false)' in block
    assert '$g.stdout | ConvertFrom-Json' not in block
    assert '1> $stdoutPath 2> $stderrPath' not in block


def test_existing_script_still_checks_runtime_and_sqlite():
    script = CHECK.read_text(encoding="utf-8")
    assert "def deploy_check(" in script
    assert "legacy_database_probe(runner, api)" in script
    assert "unique_container(runner, \"api\")" in script
    assert 'text("SELECT 1")' in script
    assert "database_probe_failed" in script


SHA = "a" * 40
CTX = ReceiptContext(SHA, "corr-1", "session-1", "DESKTOP-PDQK954")


def _gateway(inner, *, result="ok", command_exit_code=0, gateway_exit_code=None, **overrides):
    if gateway_exit_code is None:
        gateway_exit_code = command_exit_code
    value = {
        "result": result,
        "command_exit_code": command_exit_code,
        "gateway_exit_code": gateway_exit_code,
        "correlation_id": CTX.correlation_id,
        "session_id": CTX.session_id,
        "before": {"head": SHA},
        "after": {"head": SHA},
        "stdout": json.dumps(inner, separators=(",", ":")),
        "stderr": "must-never-be-public",
        "token": "secret-must-never-be-public",
    }
    value.update(overrides)
    return json.dumps(value)


def _blocked_stderr(exit_code=20, **overrides):
    value = {
        "timestamp": "2026-10-14T03:08:55+00:00",
        "correlation_id": CTX.correlation_id,
        "result": "blocked",
        "gateway_exit_code": exit_code,
        "error": "private policy detail",
    }
    value.update(overrides)
    return json.dumps(value)


def _success_inner(**overrides):
    value = {
        "deploy_check_ok": True,
        "database_ok": True,
        "environment": "dev",
        "project": "wt-pc24x7-piloto",
        "runtime_sha": SHA,
    }
    value.update(overrides)
    return value


def test_parser_accepts_verified_success():
    receipt, exit_code = build_receipt(_gateway(_success_inner()), "", 0, CTX)
    assert exit_code == 0
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_OK"
    assert receipt["reason_code"] == "ok"
    assert receipt["database_result"] == "passed"
    assert receipt["runtime_sha"] == SHA
    assert receipt["gateway_exit_code"] == receipt["command_exit_code"] == 0
    assert receipt["gateway_result"] == "ok"
    assert receipt["result_verified"] is True


def test_parser_accepts_real_command_failed_envelope():
    inner = {"ok": False, "category": "database_probe_failed"}
    receipt, exit_code = build_receipt(
        _gateway(inner, result="command_failed", command_exit_code=1),
        "",
        1,
        CTX,
    )
    assert exit_code == 1
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_FAILED"
    assert receipt["reason_code"] == "database_probe_failed"
    assert receipt["database_ok"] is None
    assert receipt["database_result"] == "unverified"
    assert receipt["runtime_sha"] is None
    assert receipt["result_verified"] is True


def test_parser_sanitizes_real_pre_execution_blocked_stderr():
    receipt, exit_code = build_receipt("", _blocked_stderr(), 20, CTX)
    assert exit_code == 1
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED"
    assert receipt["reason_code"] == "gateway_blocked"
    assert receipt["gateway_result"] == "blocked"
    assert receipt["command_exit_code"] is None
    assert receipt["command_gateway_verified"] is False
    assert "private policy detail" not in json.dumps(receipt)


@pytest.mark.parametrize(
    ("stdout", "stderr", "reason"),
    [
        ("", "", "gateway_receipt_invalid"),
        ("null", "", "gateway_receipt_invalid"),
        ("{", "", "gateway_receipt_invalid"),
        (_gateway(_success_inner(), stdout=""), "", "inner_result_missing"),
        (_gateway(_success_inner(), stdout="null"), "", "inner_result_invalid_type"),
        (_gateway(_success_inner(), stdout="{"), "", "inner_result_invalid_json"),
        ("unexpected", _blocked_stderr(), "gateway_stream_conflict"),
    ],
)
def test_parser_separates_missing_or_invalid_data_from_failure(stdout, stderr, reason):
    receipt, exit_code = build_receipt(stdout, stderr, 0 if not stderr else 20, CTX)
    assert exit_code == 1
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED"
    assert receipt["reason_code"] == reason
    assert receipt["database_result"] == "unverified"
    assert receipt["result_verified"] is False


@pytest.mark.parametrize("bad_result", [[], {}, None, 7, True])
def test_parser_rejects_non_string_gateway_result_without_exception(bad_result):
    receipt, exit_code = build_receipt(
        _gateway(_success_inner(), result=bad_result),
        "",
        0,
        CTX,
    )
    assert exit_code == 1
    assert receipt["reason_code"] == "gateway_result_invalid"


@pytest.mark.parametrize("bad_category", [[], {}, None, 7, True])
def test_parser_rejects_non_string_category_without_exception(bad_category):
    receipt, exit_code = build_receipt(
        _gateway(
            {"ok": False, "category": bad_category},
            result="command_failed",
            command_exit_code=1,
        ),
        "",
        1,
        CTX,
    )
    assert exit_code == 1
    assert receipt["reason_code"] == "inner_error_category_invalid"
    assert receipt["result_verified"] is False


@pytest.mark.parametrize(
    ("gateway_exit", "gateway_result", "command_exit", "embedded_exit"),
    [
        (1, "ok", 0, 0),
        (0, "command_failed", 1, 1),
        (1, "command_failed", 0, 0),
        (22, "command_failed", 126, 125),
    ],
)
def test_parser_rejects_divergent_exit_contract(
    gateway_exit, gateway_result, command_exit, embedded_exit
):
    receipt, exit_code = build_receipt(
        _gateway(
            {"ok": False, "category": "database_probe_failed"},
            result=gateway_result,
            command_exit_code=command_exit,
            gateway_exit_code=embedded_exit,
        ),
        "",
        gateway_exit,
        CTX,
    )
    assert exit_code == 1
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED"
    assert receipt["reason_code"] == "exit_result_mismatch"
    assert receipt["result_verified"] is False


@pytest.mark.parametrize("command_exit", [-1073741819, -9, 126, 999])
def test_parser_preserves_unbounded_integer_command_exit(command_exit):
    receipt, _ = build_receipt(
        _gateway(
            {"ok": False, "category": "command_failed"},
            result="command_failed",
            command_exit_code=command_exit,
            gateway_exit_code=command_exit,
        ),
        "",
        22,
        CTX,
    )
    assert receipt["command_exit_code"] == command_exit
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_FAILED"


@pytest.mark.parametrize("deploy_result", [None, "false", 0, 1, [], {}])
def test_parser_requires_boolean_deploy_check_result(deploy_result):
    receipt, _ = build_receipt(
        _gateway(_success_inner(deploy_check_ok=deploy_result)),
        "",
        0,
        CTX,
    )
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED"
    assert receipt["reason_code"] == "deploy_check_result_invalid"


def test_parser_observed_false_deploy_check_is_functional_failure():
    receipt, _ = build_receipt(
        _gateway(_success_inner(deploy_check_ok=False)),
        "",
        0,
        CTX,
    )
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_FAILED"
    assert receipt["reason_code"] == "deploy_check_failed"
    assert receipt["result_verified"] is True


def test_parser_rejects_sha_and_gateway_identity_divergence():
    sha_receipt, _ = build_receipt(
        _gateway(_success_inner(runtime_sha="b" * 40)),
        "",
        0,
        CTX,
    )
    identity_receipt, _ = build_receipt(
        _gateway(_success_inner(), correlation_id="other"),
        "",
        0,
        CTX,
    )
    assert sha_receipt["reason_code"] == "runtime_sha_mismatch"
    assert sha_receipt["runtime_sha"] == "b" * 40
    assert identity_receipt["reason_code"] == "gateway_identity_mismatch"
    assert identity_receipt["runtime_sha"] is None
    assert identity_receipt["database_ok"] is None


def test_parser_discards_sensitive_and_unallowlisted_fields():
    inner = _success_inner(
        stdout="inner-secret",
        stderr="inner-error",
        password="do-not-publish",
        category="attacker_controlled_reason",
    )
    receipt, _ = build_receipt(_gateway(inner), "", 0, CTX)
    encoded = json.dumps(receipt, sort_keys=True)
    assert set(receipt) == PUBLIC_KEYS
    for secret in (
        "must-never-be-public",
        "secret-must-never-be-public",
        "inner-secret",
        "inner-error",
        "do-not-publish",
        "attacker_controlled_reason",
    ):
        assert secret not in encoded



def _cli_args(stdout_path, stderr_path):
    return [
        sys.executable,
        str(PARSER),
        "--gateway-exit-code",
        "0",
        "--gateway-stdout-file",
        str(stdout_path),
        "--gateway-stderr-file",
        str(stderr_path),
        "--expected-sha",
        SHA,
        "--expected-correlation-id",
        CTX.correlation_id,
        "--expected-session-id",
        CTX.session_id,
        "--host",
        CTX.host,
    ]


def test_cli_sanitizes_post_execution_stdout(tmp_path):
    stdout_path = tmp_path / "gateway.stdout"
    stderr_path = tmp_path / "gateway.stderr"
    stdout_path.write_text(_gateway(_success_inner()), encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    completed = subprocess.run(
        _cli_args(stdout_path, stderr_path),
        capture_output=True,
        text=True,
        check=False,
    )
    receipt = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_OK"
    assert set(receipt) == PUBLIC_KEYS


def test_cli_sanitizes_utf16_pre_execution_stderr(tmp_path):
    stdout_path = tmp_path / "gateway.stdout"
    stderr_path = tmp_path / "gateway.stderr"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text(_blocked_stderr(), encoding="utf-16")
    args = _cli_args(stdout_path, stderr_path)
    args[args.index("--gateway-exit-code") + 1] = "20"
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )
    receipt = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert completed.stderr == ""
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED"
    assert receipt["reason_code"] == "gateway_blocked"
    assert "private policy detail" not in completed.stdout


@pytest.mark.parametrize("inner_ok", [None, True, 0, 1, "false", [], {}])
def test_command_failed_requires_strict_false_inner_ok(inner_ok):
    receipt, _ = build_receipt(
        _gateway(
            {"ok": inner_ok, "category": "database_probe_failed"},
            result="command_failed",
            command_exit_code=1,
        ),
        "",
        1,
        CTX,
    )
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_UNVERIFIED"
    assert receipt["reason_code"] == "inner_error_contract_invalid"


def test_cli_fails_closed_when_stream_is_missing(tmp_path):
    stdout_path = tmp_path / "missing.stdout"
    stderr_path = tmp_path / "gateway.stderr"
    stderr_path.write_text("", encoding="utf-8")
    completed = subprocess.run(
        _cli_args(stdout_path, stderr_path),
        capture_output=True,
        text=True,
        check=False,
    )
    receipt = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert receipt["reason_code"] == "gateway_stream_unavailable"


def test_cli_fails_closed_on_invalid_stream_encoding(tmp_path):
    stdout_path = tmp_path / "gateway.stdout"
    stderr_path = tmp_path / "gateway.stderr"
    stdout_path.write_bytes(b"\xff")
    stderr_path.write_text("", encoding="utf-8")
    completed = subprocess.run(
        _cli_args(stdout_path, stderr_path),
        capture_output=True,
        text=True,
        check=False,
    )
    receipt = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert receipt["reason_code"] == "gateway_stream_encoding_invalid"


@pytest.mark.parametrize("reason", [
    "runtime_dependency_missing",
    "runtime_file_missing",
    "runtime_os_error",
    "runtime_payload_invalid",
    "runtime_permission_denied",
    "runtime_subprocess_timeout",
])
def test_receipt_parser_accepts_cli_runtime_error_categories(reason):
    receipt, exit_code = build_receipt(
        _gateway(
            {"ok": False, "category": reason},
            result="command_failed", command_exit_code=1,
        ),
        "", 1, CTX,
    )
    assert exit_code == 1
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_FAILED"
    assert receipt["reason_code"] == reason
    assert receipt["result_verified"] is True
    assert receipt["runtime_sha"] is None
    assert receipt["database_result"] == "unverified"

@pytest.mark.parametrize("category", [
    "live_probe_source_unavailable",
    "live_probe_loader_unavailable",
    "live_probe_contract_invalid",
])
def test_parser_accepts_fixed_sibling_probe_errors(category):
    receipt, exit_code = build_receipt(
        _gateway(
            {"ok": False, "category": category},
            result="command_failed", command_exit_code=1,
        ),
        "", 1, CTX,
    )
    assert exit_code == 1
    assert receipt["result"] == "REQSYS_DEV_DEPLOY_CHECK_FAILED"
    assert receipt["reason_code"] == category
    assert receipt["result_verified"] is True
    assert receipt["database_result"] == "unverified"
    assert receipt["runtime_sha"] is None
