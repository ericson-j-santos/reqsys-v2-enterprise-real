from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/noteri-runtime-auto-watch.yml"


def test_noteri_runtime_auto_watch_contract() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "schedule:" in raw
    assert "cron: '*/10 * * * *'" in raw
    assert "workflow_dispatch:" in raw
    assert "runs-on: ubuntu-latest" in raw
    assert "noteri-control-plane-probe.yml" in raw
    assert "gh workflow run" in raw
    assert "--ref main" in raw
    assert "SELF_HOSTED_RUNNER_UNAVAILABLE" not in raw
    assert "gh run cancel" in raw
    assert "noteri-control-plane-$TARGET_RUN_ID" in raw
    assert "headless_ready" in raw
    assert "runner_listener_detected" in raw
    assert "runtime_active" in raw
    assert "<!-- reqsys-noteri-runtime-auto-watch -->" in raw
    assert "issue_number = Number(process.env.ISSUE_NUMBER)" in raw
    assert "reboot_performed" in raw
    assert '"reboot_performed": False' in raw
    assert "production_touched" in raw
    assert "secrets_read" in raw
    assert "Restart-Computer" not in raw
    assert "shutdown /r" not in raw
    assert "secrets." not in raw


def test_noteri_runtime_auto_watch_is_fail_closed_on_identity() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "target_run_id_mismatch" in raw
    assert "target_sha_mismatch" in raw
    assert "target_event_mismatch" in raw
    assert 'run.get("headSha") != os.environ["EXPECTED_SHA"]' in raw
    assert 'run.get("event") != "workflow_dispatch"' in raw
    assert "runner_unavailable" in raw
    assert "runner_online_headless_not_ready" in raw

def test_noteri_auto_watch_prevents_duplicate_dispatch() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "github.rest.actions.listWorkflowRuns" in raw
    assert "workflow_id: process.env.TARGET_WORKFLOW" in raw
    assert "const existing = active[0];" in raw
    assert "core.setOutput('blocked', 'true')" in raw
    assert "core.setOutput('blocked', 'false')" in raw
    for state in ("queued", "pending", "waiting", "requested", "in_progress"):
        assert f"'{state}'" in raw
    for step in (
        "Dispatch fixed Noteri probe",
        "Validate dispatched run identity",
        "Wait for self-hosted pickup",
    ):
        assert f"- name: {step}\n        if: steps.preflight.outputs.blocked != 'true'" in raw

def test_noteri_auto_watch_existing_probe_state_is_not_reported_as_success() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "existing_probe_active" in raw
    assert "steps.dispatch.outputs.run_id || steps.preflight.outputs.run_id" in raw
    assert "steps.dispatch.outputs.run_url || steps.preflight.outputs.run_url" in raw
    assert "steps.preflight.outputs.head_sha || steps.main.outputs.sha" in raw
    assert "state = \"runtime_active\" if all((ok, host_ok, listener, headless, no_rdc))" in raw
    assert "core.info(`Existing active Noteri probe ${existing.id}; dispatch suppressed`)" in raw
