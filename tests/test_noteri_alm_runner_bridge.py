from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "noteri_alm_runner_bridge.py"
RISK3 = ROOT / "scripts" / "configure_noteri_alm_runner_bridge_risk3.py"
WORKFLOW = ROOT / ".github" / "workflows" / "noteri-desktop-watchdog-recovery.yml"
GATEWAY = ROOT / ".github" / "workflows" / "reqsys-authorized-actions-gateway.yml"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bridge_is_generic_for_open_alm_prs_and_uses_stable_labels() -> None:
    raw = BRIDGE.read_text(encoding="utf-8")
    assert 'EXPECTED_HOST = "Noteri"' in raw
    assert 'TARGET_REPOSITORY = "ericson-j-santos/reqsys-powerplatform-alm"' in raw
    assert 'TARGET_BASE = "main"' in raw
    assert "TARGET_PR = 7" not in raw
    assert "TARGET_BRANCH =" not in raw
    assert "alm-pr7" not in raw
    assert 'RUNNER_LABELS = "noteri,reqsys-dev"' in raw
    assert "lowest_open_pr_with_unassigned_noteri_job" in raw
    assert "no_eligible_alm_pr" in raw
    assert "target_head_changed_during_run" in raw
    assert "RUNNER_SLOTS = 2" in raw
    assert "--ephemeral" in raw
    assert "--disableupdate" in raw


def test_bridge_pins_runner_asset_and_never_reports_registration_token() -> None:
    raw = BRIDGE.read_text(encoding="utf-8")
    assert 'RUNNER_VERSION = "2.337.0"' in raw
    assert "actions-runner-win-x64-" in raw
    assert 'RUNNER_ASSET_SHA256 = "1150692afa94e71f872017e254ea55b6eece1eece3fe7e3a6d4c93d0a1b85cfc"' in raw
    assert "registration-token" in raw
    assert '"registration_token_persisted": False' in raw
    assert '"registration_token_logged": False' in raw
    assert '"token_exposed": False' in raw
    assert "print(token)" not in raw
    assert '_emit({"token"' not in raw
    assert 'token = ""' not in raw
    assert "del token" in raw


def test_bridge_selects_lowest_open_pr_with_unassigned_noteri_job(monkeypatch) -> None:
    module = _load(BRIDGE, "noteri_alm_runner_bridge_selection")
    pulls = [
        {
            "number": 9,
            "state": "open",
            "base": {"ref": "main"},
            "draft": False,
            "head": {
                "ref": "feat/nine",
                "sha": "9" * 40,
                "repo": {"full_name": module.TARGET_REPOSITORY},
            },
        },
        {
            "number": 8,
            "state": "open",
            "base": {"ref": "main"},
            "draft": True,
            "head": {
                "ref": "feat/eight",
                "sha": "8" * 40,
                "repo": {"full_name": module.TARGET_REPOSITORY},
            },
        },
    ]
    monkeypatch.setattr(module, "_gh_list", lambda _gh, _endpoint: pulls)

    def jobs(_gh, head):
        return [
            {
                "id": 1,
                "status": "queued",
                "runner_id": None,
                "labels": sorted(module.TARGET_JOB_LABELS),
                "head": head,
            }
        ]

    monkeypatch.setattr(module, "_target_job_state", jobs)
    target, observed = module._select_target_pr(Path("gh"))
    assert target["number"] == 8
    assert target["branch"] == "feat/eight"
    assert target["head"] == "8" * 40
    assert target["draft"] is True
    assert observed[0]["status"] == "queued"


def test_bridge_ignores_pr_without_unassigned_noteri_job(monkeypatch) -> None:
    module = _load(BRIDGE, "noteri_alm_runner_bridge_no_candidate")
    pulls = [
        {
            "number": 8,
            "state": "open",
            "base": {"ref": "main"},
            "draft": False,
            "head": {
                "ref": "feat/eight",
                "sha": "8" * 40,
                "repo": {"full_name": module.TARGET_REPOSITORY},
            },
        }
    ]
    monkeypatch.setattr(module, "_gh_list", lambda _gh, _endpoint: pulls)
    monkeypatch.setattr(
        module,
        "_target_job_state",
        lambda _gh, _head: [
            {
                "id": 1,
                "status": "in_progress",
                "runner_id": 123,
                "labels": sorted(module.TARGET_JOB_LABELS),
            }
        ],
    )
    with pytest.raises(module.BridgeError, match="nenhuma PR aberta"):
        module._select_target_pr(Path("gh"))


def test_bridge_revalidates_frozen_pr_branch_and_head(monkeypatch) -> None:
    module = _load(BRIDGE, "noteri_alm_runner_bridge_target")
    target_head = "a" * 40

    def valid_target(_gh, _endpoint):
        return {
            "number": 12,
            "state": "open",
            "base": {"ref": "main"},
            "head": {
                "ref": "feat/target",
                "sha": target_head,
                "repo": {"full_name": module.TARGET_REPOSITORY},
            },
        }

    monkeypatch.setattr(module, "_gh_json", valid_target)
    assert module._pr_target(Path("gh"), 12, "feat/target") == target_head

    def wrong_branch(_gh, _endpoint):
        payload = valid_target(_gh, _endpoint)
        payload["head"]["ref"] = "unexpected"
        return payload

    monkeypatch.setattr(module, "_gh_json", wrong_branch)
    with pytest.raises(module.BridgeError, match="branch da PR #12 mudou"):
        module._pr_target(Path("gh"), 12, "feat/target")


def test_bridge_cancels_only_active_stale_runs_for_selected_branch(monkeypatch) -> None:
    module = _load(BRIDGE, "noteri_alm_runner_bridge_stale")
    current = "c" * 40
    runs = [
        {"id": 11, "head_sha": "a" * 40, "status": "queued", "pull_requests": []},
        {"id": 12, "head_sha": current, "status": "queued", "pull_requests": []},
        {"id": 13, "head_sha": "b" * 40, "status": "completed", "pull_requests": []},
    ]
    monkeypatch.setattr(module, "_workflow_runs_for_branch", lambda _gh, _branch: runs)
    calls: list[list[str]] = []

    def fake_run(_gh, args, *, timeout=30):
        calls.append(args)
        return __import__("subprocess").CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(module, "_run_gh", fake_run)
    cancelled = module._cancel_stale_runs(
        Path("gh"),
        target_pr=8,
        target_branch="feat/eight",
        expected_head=current,
    )
    assert cancelled == [11]
    assert calls == [
        [
            "api",
            "--method",
            "POST",
            f"repos/{module.TARGET_REPOSITORY}/actions/runs/11/cancel",
        ]
    ]


def test_bridge_classifies_terminal_and_success_runs() -> None:
    module = _load(BRIDGE, "noteri_alm_runner_bridge_runs")
    success = [
        {"status": "completed", "conclusion": "success"},
        {"status": "completed", "conclusion": "skipped"},
    ]
    assert module._all_runs_terminal(success)
    assert module._all_runs_success(success)
    failed = [{"status": "completed", "conclusion": "failure"}]
    assert module._all_runs_terminal(failed)
    assert not module._all_runs_success(failed)
    pending = [{"status": "queued", "conclusion": None}]
    assert not module._all_runs_terminal(pending)


def test_risk3_action_is_exact_temporary_repo_scoped_and_dev_only(tmp_path: Path) -> None:
    module = _load(RISK3, "configure_noteri_alm_runner_bridge_risk3")
    assert module.ACTION_ID == "reqsys.noteri-alm-runner-bridge.dev"
    assert module.SCOPE == "repo://ericson-j-santos/reqsys-powerplatform-alm/actions/runner/dev"
    assert "/pr7" not in module.SCOPE
    assert module.COMMAND == ["python", "scripts/noteri_alm_runner_bridge.py"]
    path = tmp_path / "owner-risk3-exceptions.local.json"
    enabled = module.enable(path, 15)
    assert enabled["status"] == "enabled"
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    action = payload["actions"][module.ACTION_ID]
    assert action["environment"] == "dev"
    assert action["scope"] == module.SCOPE
    assert action["command"] == module.COMMAND
    disabled = module.disable(path)
    assert disabled["removed"] is True


def test_workflow_exposes_fixed_generic_alm_bridge_mode() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "- alm-runner-bootstrap" in raw
    assert "alm-runner-bootstrap:" in raw
    assert "inputs.mode == 'alm-runner-bootstrap'" in raw
    assert "reqsys.noteri-alm-runner-bridge.dev" in raw
    assert "repo://ericson-j-santos/reqsys-powerplatform-alm/actions/runner/dev" in raw
    assert "/runner/dev/pr7" not in raw
    assert "ENABLE-NOTERI-ALM-RUNNER-BRIDGE-ONCE" in raw
    assert "DISABLE-NOTERI-ALM-RUNNER-BRIDGE-ONCE" in raw
    assert "owner_risk3_gateway.py" in raw
    assert "configure_noteri_alm_runner_bridge_risk3.py" in raw
    assert "python312._pth" in raw
    assert '$rulesScripts = Join-Path $env:GITHUB_WORKSPACE "_rules\\scripts"' in raw
    assert "RISK3_CLEANUP_NOT_REQUIRED session_not_materialized" in raw
    assert "PICKUP_VERIFIED" in raw
    assert "TARGET_PR_INVALID" in raw
    assert "TARGET_BRANCH_INVALID" in raw
    assert "RUNNER_PICKUP_NOT_VERIFIED" in raw


def test_alm_workflow_risk3_timeout_respects_gateway_contract() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    alm_block = raw.split("  alm-runner-bootstrap:", 1)[1]
    assert '"--timeout", "900",' in alm_block
    assert '"--timeout", "960",' not in alm_block


def test_authorized_gateway_maps_exact_command_to_existing_workflow_mode() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")
    assert "github.event.comment.body == '/reqsys run noteri-alm-runner-bootstrap'" in raw
    assert "'/reqsys run noteri-alm-runner-bootstrap')" in raw
    assert "target='noteri-desktop-watchdog-recovery.yml'" in raw
    assert "mode='alm-runner-bootstrap'" in raw
    assert "runner-recover|runner-bootstrap|runner-canary|reboot-once|alm-runner-bootstrap" in raw
