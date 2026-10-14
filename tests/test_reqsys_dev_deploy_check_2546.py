"""Fixed read-only DEV deploy check — issue #2546."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GW = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
WF = ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml"
CHECK = ROOT / "scripts/dev_runtime_recovery.py"
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
        "REQSYS_DEV_DEPLOY_CHECK_OK",
        "REQSYS_DEV_DEPLOY_CHECK_BLOCKED",
        TASK_ID,
    )
    for item in required:
        assert item in block
    for bad in ("docker compose up", "docker compose down", "requeue",
                "POST /v1/claims", "-f mode=prod"):
        assert bad not in block


def test_sha_db_and_negative_evidence_fail_closed():
    block = _job()
    expected = (
        '$g.before.head -ne $env:ANCHOR_SHA',
        '$g.after.head -ne $env:ANCHOR_SHA',
        '$inner.runtime_sha -eq $env:ANCHOR_SHA',
        '$inner.database_ok -eq $true',
        '$inner.environment -eq "dev"',
        '$inner.project -eq "wt-pc24x7-piloto"',
        'if (-not $ok) { throw "DEPLOY_CHECK_BLOCKED:$reason" }',
        'throw "DEPLOY_CHECK_GATEWAY_RECEIPT_MISSING"',
        'throw "DEPLOY_CHECK_EVIDENCE_MISSING"',
        'throw "DEPLOY_CHECK_EVIDENCE_INVALID"',
        'throw "DEPLOY_CHECK_SAFETY_INVALID"',
        "if: always()",
    )
    for item in expected:
        assert item in block
    assert '[System.Text.UTF8Encoding]::new($false)' in block


def test_existing_script_still_checks_runtime_and_sqlite():
    script = CHECK.read_text(encoding="utf-8")
    assert "def deploy_check(" in script
    assert "legacy_database_probe(runner, api)" in script
    assert "unique_container(runner, \"api\")" in script
    assert 'text("SELECT 1")' in script
    assert "database_probe_failed" in script
