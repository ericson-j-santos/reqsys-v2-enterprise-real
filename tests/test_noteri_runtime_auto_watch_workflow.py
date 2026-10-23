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

def _run_preflight_case(
    *,
    history: list[dict] | None = None,
    jobs: list[dict] | None = None,
    active: list[dict] | None = None,
    event: str = "schedule",
    actor: str = "github-actions[bot]",
    override: bool = False,
    completed_api_error: bool = False,
) -> tuple[int, dict]:
    """Execute the actual inline github-script with a fake GitHub API, not a reimplementation."""
    import json
    import os
    import subprocess

    import yaml

    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["watch"]["steps"]
    admission = next(step for step in steps if step["name"] == "Avoid duplicate active Noteri probe")
    source = admission["with"]["script"]
    fixture = {
        "history": history or [],
        "jobs": jobs or [],
        "active": active or [],
        "event": event,
        "actor": actor,
        "override": override,
        "completedApiError": completed_api_error,
    }
    harness = r"""
const f = JSON.parse(process.env.TEST_NOTERI_PROBE_FIXTURE);
const output = {};
const core = { setOutput: (name, value) => { output[name] = value; }, info: () => {} };
const context = {
  repo: { owner: 'ericson-j-santos', repo: 'reqsys-v2-enterprise-real' },
  eventName: f.event,
  actor: f.actor,
  payload: { inputs: { probe_after_change: f.override ? 'true' : 'false' } },
};
process.env.TARGET_WORKFLOW = 'noteri-control-plane-probe.yml';
const github = {
  rest: {
    actions: {
      listWorkflowRuns: async ({ status }) => {
        if (status === 'completed') {
          if (f.completedApiError) throw new Error('API_UNAVAILABLE');
          return { data: { workflow_runs: f.history } };
        }
        return { data: { workflow_runs: f.active.filter(run => run.status === status) } };
      },
      listJobsForWorkflowRun: async () => ({ data: { jobs: f.jobs } }),
    },
  },
};
(async () => {
"""
    harness += source + r"""
})().then(() => {
  process.stdout.write(JSON.stringify(output));
}).catch(error => {
  process.stderr.write(String(error));
  process.exitCode = 17;
});
"""
    env = dict(os.environ, TEST_NOTERI_PROBE_FIXTURE=json.dumps(fixture))
    result = subprocess.run(["node", "-e", harness], env=env, check=False,
                            text=True, capture_output=True, timeout=20)
    return result.returncode, json.loads(result.stdout) if result.stdout else {}


def _prior_probe(*, minutes_ago: int, conclusion: str = "cancelled") -> dict:
    from datetime import datetime, timedelta, timezone

    return {
        "id": 123456,
        "html_url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/123456",
        "head_sha": "a" * 40,
        "head_branch": "main",
        "created_at": (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(),
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": conclusion,
    }


def test_not_parameters_alone_open_a_new_probe() -> None:
    from datetime import datetime, timezone

    failed = _prior_probe(minutes_ago=4)
    code, output = _run_preflight_case(history=[failed])
    assert code == 0
    assert output["blocked"] == "true"
    assert output["block_reason"] == "runner_unavailable_cooldown"
    assert output["run_id"] == "123456"
    # A confirmed physical pickup is a material change even if the run ended cancelled.
    code, output = _run_preflight_case(history=[failed], jobs=[
        {"runner_id": 22, "runner_name": "Noteri", "started_at": datetime.now(timezone.utc).isoformat()}
    ])
    assert code == 0
    assert output["blocked"] == "false"


def test_noteri_circuit_breaker_half_open_and_positive_recovery() -> None:

    code, output = _run_preflight_case(history=[_prior_probe(minutes_ago=90)])
    assert code == 0 and output["blocked"] == "false"
    code, output = _run_preflight_case(history=[_prior_probe(minutes_ago=3, conclusion="success")])
    assert code == 0 and output["block_reason"] == "runner_unavailable_cooldown"
    code, output = _run_preflight_case(history=[_prior_probe(minutes_ago=5)], event="workflow_dispatch",
                                       actor="ericson-j-santos", override=True)
    assert code == 0 and output["blocked"] == "false"
    code, output = _run_preflight_case(history=[_prior_probe(minutes_ago=5)], event="workflow_dispatch",
                                       actor="another-user", override=True)
    assert code == 0 and output["block_reason"] == "runner_unavailable_cooldown"
    code, output = _run_preflight_case()
    assert code == 0 and output["blocked"] == "false"


def test_noteri_circuit_breaker_reuses_active_and_fails_closed_on_api_error() -> None:
    prior = _prior_probe(minutes_ago=2)
    active = {**prior, "id": 98765, "status": "queued"}
    code, output = _run_preflight_case(active=[active], completed_api_error=True)
    assert code == 0 and output["block_reason"] == "existing_probe_active"
    code, output = _run_preflight_case(completed_api_error=True)
    assert code != 0 and "blocked" not in output


def test_noteri_circuit_breaker_contract_is_bound_to_monitor_receipt() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "probe_after_change:" in raw
    assert "ownerRecoverySignal" in raw
    assert "runner_unavailable_cooldown" in raw
    assert "listJobsForWorkflowRun" in raw
    assert "steps.preflight.outputs.block_reason || steps.pickup.outputs.state" in raw
    assert "NOTERI_PROBE_TIMESTAMP_UNTRUSTED" in raw
    assert "cron: '*/10 * * * *'" in raw
