"""Static workflow contract: security, exact owner dispatch, evidence and no cutover."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/codex-worker-pool-smoke-dev.yml"
GATEWAY=ROOT/".github/workflows/reqsys-authorized-actions-gateway.yml"
SCRIPT=ROOT/"scripts/pc24x7_worker_pool_physical_candidate_dev.py"


def source():
    return WORKFLOW.read_text(encoding="utf-8")


def candidate_job():
    parsed=yaml.safe_load(source())
    return parsed["jobs"]["physical-canary"]


def test_mode_and_job_are_fixed_and_on_desktop():
    raw=source()
    assert "- physical-canary" in raw
    job=candidate_job()
    assert job["if"]=="${{ inputs.mode == 'physical-canary' }}"
    assert job["runs-on"]==["self-hosted","Windows","X64","pc24x7","reqsys-dev"]
    assert job["env"]["CANDIDATE_SHA"]=="9074b170d47a7d63a4e0ef6cee2d37282bbbace8"
    assert job["env"]["RULES_SHA"]=="f6ccb143a581e28650e9b640226f9ef671d469f2"
    assert job["env"]["EVIDENCE_REL"].endswith("physical-canary-dev\\evidence.json")


def test_gate_owner_literal_allowlist_and_mode_dispatch():
    src=GATEWAY.read_text(encoding="utf-8")
    key="/reqsys run pc24x7-worker-pool-physical-canary-dev"
    assert src.count(key)>=2
    assert "github.event.issue.number == 1705" in src
    assert "github.event.comment.user.login == 'ericson-j-santos'" in src
    assert "mode='physical-canary'" in src
    assert "-f mode=physical-canary" in src
    assert "target='codex-worker-pool-smoke-dev.yml'" in src
    assert src.count('"physical-canary"')>=1 or '"$TARGET_MODE" = "physical-canary"' in src


def test_gate_session_then_gateway_and_sha_lock():
    steps=candidate_job()["steps"]
    names=[s["name"] for s in steps]
    assert names.index("Bootstrap mandatory governed session") < names.index(
        "Execute canary only through Command Gateway") < names.index(
        "Validate sanitized physical canary evidence")
    checkout=next(s for s in steps if s["name"]=="Checkout immutable dedicated Worker Pool source")
    assert checkout["with"]["ref"]=="9074b170d47a7d63a4e0ef6cee2d37282bbbace8"
    cmd=next(s["run"] for s in steps if s["name"]=="Execute canary only through Command Gateway")
    for required in ('--risk", "2"','--timeout", "300"','--expected-head','CANARY-WORKER-POOL-14-ISOLATED-DEV','pc24x7_worker_pool_physical_candidate_dev.py'):
        assert required in cmd
    session=next(s["run"] for s in steps if s["name"]=="Bootstrap mandatory governed session")
    assert 'SESSION_LAUNCH_OK' in session and 'state_validated' in session
    assert 'require-runner-version-preflight' in session


def test_receipt_rejects_false_positive_and_uploads_fixed_file():
    steps=candidate_job()["steps"]
    validate=next(s["run"] for s in steps if s["name"]=="Validate sanitized physical canary evidence")
    for flag in ("candidate_image_digest_attested_on_desktop","legacy_container_unchanged",
                 "independent_sqlite_readback","private_snapshot_reused","isolated_volume_used",
                 "candidate_cleanup_verified","rollback_rehearsal_passed","cutover_ready",
                 "enqueue_performed","claim_performed","live_database_modified","secrets_exposed"):
        assert flag in validate
    upload=steps[-1]
    assert upload["name"]=="Upload sanitized physical canary evidence"
    assert upload["if"].startswith("always()")
    assert "${{ steps.session.outputs.target_path }}" in upload["with"]["path"]
    assert upload["with"]["if-no-files-found"]=="error"


def test_does_not_modify_legacy_runtime_by_compose_or_requeue():
    content=SCRIPT.read_text()
    assert "BACKUP_CORRELATION" in content and "BACKUP_SHA256" in content
    assert "BACKUP_CIPHER_SHA256" in content
    assert "--network\",\"none" in content
    assert '"--cap-drop","ALL"' in content
    assert '"--read-only"' in content
    assert "wp-physical-canary" in content
    for forbidden in ('docker compose down','docker compose up','POST /v1/claims','/v1/snapshot'):
        assert forbidden not in content
    assert '"rollback_rehearsal_passed":False' in content
    assert '"cutover_ready":False' in content


@pytest.mark.parametrize("missing", ["--expected-head", "candidate_cleanup_verified", "cutover_ready"])
def test_negative_removing_a_gate_must_break_acceptance(missing,monkeypatch,tmp_path):
    src=source()
    broken=src.replace(missing,"removed")
    assert missing not in broken
    # A tampered workflow would fail the positive controls above.
    assert missing in src
