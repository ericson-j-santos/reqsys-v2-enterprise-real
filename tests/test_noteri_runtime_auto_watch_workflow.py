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
    assert "worker_pool_json" in raw
    assert "reqsys-worker-pool:" in raw
    assert "no_material_progress_over_5m" in raw
    assert "pending_without_eligible_executor" in raw
    assert "worker_registry_stale" in raw
    assert "heartbeat e lease isolados não contam como progresso" in raw


def test_noteri_runtime_auto_watch_is_fail_closed_on_identity() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "target_run_id_mismatch" in raw
    assert "target_sha_mismatch" in raw
    assert "target_event_mismatch" in raw
    assert 'run.get("headSha") != os.environ["EXPECTED_SHA"]' in raw
    assert 'run.get("event") != "workflow_dispatch"' in raw
    assert "runner_unavailable" in raw
    assert "runner_online_headless_not_ready" in raw
