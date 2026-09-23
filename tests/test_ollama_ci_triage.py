from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ollama_ci_triage.py"
SPEC = importlib.util.spec_from_file_location("ollama_ci_triage", SCRIPT)
assert SPEC and SPEC.loader
triage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(triage)

SERVICE_ROOT = ROOT / "services" / "codex-worker-pool"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))
from app.store import ConflictError, WorkerPoolStore  # noqa: E402


def technical(confidence: float = 0.9) -> dict[str, Any]:
    return {
        "category": "code",
        "confidence": confidence,
        "root_cause": "falha determinística de parser",
        "recommended_action": "corrigir parser e reexecutar testes",
        "evidence": ["test_parser failed"],
    }


def run(name: str = "CI — ReqSys v2 Enterprise") -> dict[str, Any]:
    return {"name": name, "conclusion": "failure"}


def deterministic(*categories: str) -> dict[str, Any]:
    selected = categories or ("test_failure",)
    return {"matches": [{"category": category} for category in selected]}


def pr() -> dict[str, Any]:
    return {
        "number": 1890,
        "state": "open",
        "draft": False,
        "target_branch": "fix/ci-1890",
        "head_sha": "a" * 40,
        "run_head_sha": "a" * 40,
        "same_repository": True,
        "sha_current": True,
    }


@pytest.mark.parametrize("category", ["security", "governance", "transient", "unknown"])
def test_non_technical_categories_never_auto_escalate(category: str) -> None:
    payload = technical()
    payload["category"] = category
    assert triage.escalation_policy(payload, run(), pr(), deterministic())["eligible"] is False


def test_low_confidence_never_auto_escalates() -> None:
    assert triage.escalation_policy(technical(0.74), run(), pr(), deterministic())["reason"] == "confidence_below_threshold"


def test_sensitive_workflow_is_analysis_only() -> None:
    assert triage.escalation_policy(technical(), run("Governance Quality Gates"), pr(), deterministic())["reason"] == "sensitive_workflow"


def test_stale_sha_and_external_fork_fail_closed() -> None:
    stale = pr()
    stale["sha_current"] = False
    assert triage.escalation_policy(technical(), run(), stale, deterministic())["reason"] == "stale_ci_sha"
    external = pr()
    external["same_repository"] = False
    assert triage.escalation_policy(technical(), run(), external, deterministic())["reason"] == "external_fork_blocked"


def test_valid_technical_failure_targets_same_pr_branch() -> None:
    decision = triage.escalation_policy(technical(), run(), pr(), deterministic())
    assert decision["eligible"] is True
    assert decision["target_branch"] == "fix/ci-1890"


def test_model_cannot_override_deterministic_transient_signal() -> None:
    decision = triage.escalation_policy(technical(), run(), pr(), deterministic("timeout"))
    assert decision == {"eligible": False, "reason": "deterministic_block:timeout"}


def test_model_without_known_technical_signal_does_not_auto_escalate() -> None:
    decision = triage.escalation_policy(technical(), run(), pr(), {"matches": []})
    assert decision == {"eligible": False, "reason": "deterministic_signal_missing"}


def test_invalid_ollama_output_degrades_fail_closed() -> None:
    report = {
        "matches": [
            {
                "pattern_id": "pytest_failure",
                "category": "test_failure",
                "severity": "high",
                "confidence": 0.99,
                "recommended_action": "corrigir teste",
            }
        ]
    }
    degraded = triage.degraded_triage("ollama_structured_output_invalid", report)
    assert degraded["category"] == "unknown"
    assert degraded["confidence"] == 0.0
    assert "ollama_degraded:ollama_structured_output_invalid" in degraded["evidence"]
    decision = triage.escalation_policy(degraded, run(), pr(), report)
    assert decision == {"eligible": False, "reason": "category_unknown_not_auto_fixable"}


@pytest.mark.parametrize(
    "reason",
    [
        "ollama_structured_output_invalid",
        "ollama_invalid_json",
        "ollama_model_unavailable",
        "ollama_unreachable",
        "ollama_http_500",
    ],
)
def test_runtime_ollama_failures_are_degradable(reason: str) -> None:
    assert triage.is_degradable_ollama_error(triage.TriageError(reason)) is True


def test_ollama_url_policy_error_is_not_degradable() -> None:
    assert triage.is_degradable_ollama_error(triage.TriageError("ollama_url_not_loopback")) is False


@pytest.mark.parametrize("branch", ["main", "master", "develop", "../escape", "bad//branch", "refs heads"])
def test_target_branch_guard(branch: str) -> None:
    with pytest.raises(triage.TriageError):
        triage.validate_target_branch(branch)


def test_log_sanitization_masks_credentials() -> None:
    secret_name = "to" + "ken"
    fake_github_token = "g" + "hp_" + ("a" * 30)
    bearer = "Be" + "arer"
    value = triage.sanitize_log(
        f"{secret_name}=abc123\nAuthorization: {bearer} {fake_github_token}"
    )
    assert "abc123" not in value
    assert fake_github_token not in value
    assert "[REDACTED]" in value


def test_enqueue_proves_replay_readback_and_same_branch() -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []
    target = "fix/ci-1890"
    task = {
        "task_id": "cwp-test",
        "repository": "owner/repo",
        "issue_number": 1890,
        "request_id": triage.worker_request_id("owner/repo", 1890, "a" * 40),
        "base_sha": "a" * 40,
        "branch": target,
        "state": "queued",
    }

    def fake(method: str, url: str, token: str, payload: dict[str, Any] | None) -> tuple[int, dict[str, Any]]:
        assert token == "worker-token"
        calls.append((method, url, payload))
        if url.endswith("/health"):
            return 200, {"status": "healthy"}
        if method == "POST" and len([x for x in calls if x[0] == "POST"]) == 1:
            assert payload and payload["target_branch"] == target
            return 201, {"created": True, "task": dict(task)}
        if method == "POST":
            return 200, {"created": False, "task": dict(task)}
        if method == "GET":
            return 200, dict(task)
        raise AssertionError((method, url))

    result = triage.enqueue_worker_pool(
        repository="owner/repo",
        pr_number=1890,
        head_sha="a" * 40,
        target_branch=target,
        correlation_id="corr",
        pool_url="http://127.0.0.1:8097",
        token="worker-token",
        request_fn=fake,
    )
    assert result["status"] == "enqueued"
    assert result["replay_created"] is False
    assert result["independent_readback"] is True
    assert result["branch"] == target


def test_worker_pool_target_branch_is_retrocompatible_and_idempotent(tmp_path: Path) -> None:
    store = WorkerPoolStore(tmp_path / "pool.db")
    legacy, _ = store.enqueue_task(
        repository="owner/repo", issue_number=1, request_id="legacy",
        correlation_id="legacy", base_sha="1" * 40,
    )
    assert legacy["branch"].startswith("codex/issue-1-")

    task, created = store.enqueue_task(
        repository="owner/repo", issue_number=1890, request_id="ci-pr",
        correlation_id="corr", base_sha="a" * 40, target_branch="fix/ci-1890",
    )
    assert created is True
    assert task["branch"] == "fix/ci-1890"

    replay, replay_created = store.enqueue_task(
        repository="owner/repo", issue_number=1890, request_id="ci-pr",
        correlation_id="replay", base_sha="a" * 40, target_branch="fix/ci-1890",
    )
    assert replay_created is False
    assert replay["task_id"] == task["task_id"]

    with pytest.raises(ConflictError, match="target_branch divergente"):
        store.enqueue_task(
            repository="owner/repo", issue_number=1890, request_id="ci-pr",
            correlation_id="bad-replay", base_sha="a" * 40, target_branch="fix/other",
        )


def test_worker_pool_rejects_protected_target_branch(tmp_path: Path) -> None:
    store = WorkerPoolStore(tmp_path / "pool.db")
    with pytest.raises(ValueError, match="target_branch protegida"):
        store.enqueue_task(
            repository="owner/repo", issue_number=1890, request_id="protected",
            correlation_id="corr", base_sha="a" * 40, target_branch="main",
        )


@pytest.mark.parametrize(
    "reason",
    [
        "github_http_403",
        "github_http_429",
        "github_unreachable",
        "github_invalid_json",
        "github_job_log_http_403",
        "github_job_log_download_failed",
    ],
)
def test_optional_triage_infrastructure_failures_are_degradable(reason: str) -> None:
    assert triage.is_degradable_triage_infrastructure_error(triage.TriageError(reason)) is True


def test_main_degrades_github_403_without_second_red_ci(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "evidence.json"

    def fail_execute(args):
        raise triage.TriageError("github_http_403")

    monkeypatch.setattr(triage, "execute", fail_execute)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ollama_ci_triage.py",
            "--repository",
            "owner/repo",
            "--run-id",
            "123",
            "--output",
            str(output),
        ],
    )

    assert triage.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["result"] == "OLLAMA_CI_TRIAGE_DEGRADED"
    assert payload["degraded_reason"] == "github_http_403"
    assert payload["escalation"] == {
        "eligible": False,
        "reason": "triage_infrastructure_degraded",
    }
    assert payload["worker_pool"] is None
