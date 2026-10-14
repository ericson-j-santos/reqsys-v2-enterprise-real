"""ReqSys #2546: fixed read-only DEV deploy-check admission and workflow."""
from __future__ import annotations
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from scripts.authorized_teams_e2e_admission import AdmissionError, DEV_DEPLOY_CHECK_COMMAND, decide
ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
def instant(delta=0):
    return (datetime(2026, 10, 13, 20, tzinfo=timezone.utc) + timedelta(seconds=delta)).isoformat()
def event(cid, delta=0, body=DEV_DEPLOY_CHECK_COMMAND, owner="ericson-j-santos"):
    return {"action": "created", "issue": {"number": 1705},
            "comment": {"id": cid, "created_at": instant(delta), "body": body, "user": {"login": owner}}}
def record(cid, delta=0):
    return {"id": cid, "created_at": instant(delta), "user_login": "ericson-j-santos"}

def test_owner_first_admission_duplicate_and_cooldown():
    comments = [record(10), record(11, 19)]
    first = decide(event(10), comments, expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)
    replay = decide(event(11, 19), list(reversed(comments)), expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)
    later = decide(event(12, 121), [record(10), record(12, 121)], expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)
    assert first["admitted"] and first["canonical_comment_id"] == 10
    assert not replay["admitted"] and replay["canonical_comment_id"] == 10
    assert later["admitted"]

@pytest.mark.parametrize("changes,code", [
    ({"owner": "intruder"}, "comment_author_not_allowlisted"),
    ({"body": "/reqsys run arbitrary"}, "command_not_allowlisted"),
])
def test_unauthorized_comment_fails_closed(changes, code):
    with pytest.raises(AdmissionError, match=code):
        decide(event(10, **changes), [record(10)], expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)

def test_incomplete_readback_fails_closed():
    with pytest.raises(AdmissionError, match="current_comment_not_uniquely_read_back"):
        decide(event(10), [], expected_sha=SHA, command=DEV_DEPLOY_CHECK_COMMAND)

def test_argparse_accepts_exact_command_not_arbitrary(tmp_path):
    ef, cf, of = (tmp_path / name for name in ("event.json", "comments.jsonl", "output"))
    ef.write_text(json.dumps(event(100)), encoding="utf-8")
    cf.write_text(json.dumps(record(100)) + "\n", encoding="utf-8")
    argv = [sys.executable, str(ROOT / "scripts/authorized_teams_e2e_admission.py"),
            "--event-file", str(ef), "--comments-file", str(cf),
            "--expected-sha", SHA, "--command", DEV_DEPLOY_CHECK_COMMAND, "--github-output", str(of)]
    ok = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert ok.returncode == 0 and "admitted=true" in of.read_text()
    of.unlink()
    bad = subprocess.run([*argv[:-3], "/reqsys run arbitrary", *argv[-2:]],
                         cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert bad.returncode != 0 and not of.exists()

def test_github_exact_sha_session_and_negative_contract():
    gw = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text()
    wf = (ROOT / ".github/workflows/codex-worker-pool-smoke-dev.yml").read_text()
    assert "github.event.comment.body == '/reqsys run pc24x7-dev-deploy-check'" in gw
    assert "mode='dev-deploy-check'" in gw and "-f mode=dev-deploy-check" in gw
    assert "steps.route.outputs.mode == 'dev-deploy-check'" in gw
    assert "\n  dev-deploy-check:" in wf
    job = wf.split("\n  dev-deploy-check:", 1)[1]
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in job
    assert "SESSION_LAUNCH_OK" in job and "--require-runner-version-preflight" in job
    assert "command_gateway.py" in job and '"python", $script, "deploy-check"' in job
    assert '"--expected-sha", $env:ANCHOR_SHA' in job and '"--risk", "1"' in job
    assert "DEPLOY_CHECK_GATEWAY_REFUSED" in job and "DEPLOY_CHECK_READBACK_MISMATCH" in job
    assert "REQSYS_DEV_DEPLOY_CHECK_READBACK_OK" in job and "DEPLOY_CHECK_EVIDENCE_INVALID" in job
    assert "runtime_mutated = $false" in job and "production_touched = $false" in job
    assert "if: always()" in job and "docker compose up" not in job.lower()
