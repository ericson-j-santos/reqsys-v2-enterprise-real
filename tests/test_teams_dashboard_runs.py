from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from sys import path

import pytest

path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.teams_dashboard_runs import WorkflowRunQueryError, collect_recent_workflow_runs

CUTOFF = datetime(2026, 10, 4, tzinfo=timezone.utc)


def item(when: str, status: str = "completed") -> dict:
    return {"created_at": when, "status": status, "event": "push"}


def test_positive_returns_recent_completed_and_stops_at_cutoff():
    seen = []
    def runner(command, **kwargs):
        seen.append(command[-1])
        payload = [item("2026-11-03T00:00:00Z") for _ in range(99)] + [item("2026-10-03T00:00:00Z")]
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")
    result = collect_recent_workflow_runs("user/repo", "delivery.yml", CUTOFF, runner=runner)
    assert len(result) == 99
    assert len(seen) == 1
    assert "page=1" in seen[0]


def test_retries_transient_502_and_succeeds():
    calls, sleeps = [], []
    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="gh: Server Error (HTTP 502)")
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps([item("2026-11-03T00:00:00Z")]), stderr="")
    assert len(collect_recent_workflow_runs("user/repo", "delivery.yml", CUTOFF, runner=runner, sleeper=sleeps.append)) == 1
    assert len(calls) == 2 and sleeps == [1]


def test_rejects_permanent_auth_error_without_retry():
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="HTTP 403")
    with pytest.raises(WorkflowRunQueryError, match="API falhou"):
        collect_recent_workflow_runs("user/repo", "delivery.yml", CUTOFF, runner=runner)
    assert len(calls) == 1


def test_rejects_out_of_order_pages():
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps([
            item("2026-11-01T00:00:00Z"), item("2026-11-02T00:00:00Z")
        ]), stderr="")
    with pytest.raises(WorkflowRunQueryError, match="fora de ordem"):
        collect_recent_workflow_runs("user/repo", "delivery.yml", CUTOFF, runner=runner)


def test_rejects_incomplete_horizon():
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps([item("2026-11-03T00:00:00Z")] * 100), stderr="")
    with pytest.raises(WorkflowRunQueryError, match="Limite de páginas"):
        collect_recent_workflow_runs("user/repo", "delivery.yml", CUTOFF, runner=runner, max_pages=1)


def test_rejects_timeout_after_bounded_retries():
    calls = []
    def runner(command, **kwargs):
        calls.append(command)
        raise subprocess.TimeoutExpired(command, timeout=30)
    with pytest.raises(WorkflowRunQueryError, match="API timeout"):
        collect_recent_workflow_runs("user/repo", "delivery.yml", CUTOFF, runner=runner, sleeper=lambda _: None)
    assert len(calls) == 3


def test_invalid_json_rejected():
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="invalid", stderr="")
    with pytest.raises(WorkflowRunQueryError, match="JSON inválido"):
        collect_recent_workflow_runs("user/repo", "delivery.yml", CUTOFF, runner=runner)
