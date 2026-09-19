from __future__ import annotations

from scripts import pc24x7_github_runner_recovery as recovery


def test_runner_probe_stopped_without_start(monkeypatch) -> None:
    monkeypatch.setattr(recovery, "listener_processes", lambda: [])
    monkeypatch.setattr(recovery, "runner_services", lambda: [])
    monkeypatch.setattr(recovery, "runner_tasks", lambda: [])
    monkeypatch.setattr(recovery, "runner_roots", lambda: [])

    evidence = recovery.execute(start=False)

    assert evidence["status"] == "stopped"
    assert evidence["runner_started"] is False
    assert evidence["production_touched"] is False
    assert evidence["secret_value_exposed"] is False


def test_runner_start_fails_closed_when_target_is_ambiguous(monkeypatch) -> None:
    monkeypatch.setattr(recovery, "listener_processes", lambda: [])
    monkeypatch.setattr(recovery, "runner_services", lambda: [])
    monkeypatch.setattr(
        recovery,
        "runner_tasks",
        lambda: [{"task_name": "runner-a"}, {"task_name": "runner-b"}],
    )
    monkeypatch.setattr(recovery, "runner_roots", lambda: [])

    evidence = recovery.execute(start=True)

    assert evidence["status"] == "blocked"
    assert evidence["reason"] == "runner_target_ambiguous_or_missing"
    assert evidence["production_touched"] is False


def test_runner_starts_single_governed_task(monkeypatch) -> None:
    process_reads = iter([
        [],
        [{"pid": 4242, "name": "Runner.Listener.exe"}],
    ])
    monkeypatch.setattr(recovery, "listener_processes", lambda: next(process_reads))
    monkeypatch.setattr(recovery, "runner_services", lambda: [])
    monkeypatch.setattr(recovery, "runner_tasks", lambda: [{"task_name": r"\\Automation\\GitHubRunner"}])
    monkeypatch.setattr(recovery, "runner_roots", lambda: [])
    monkeypatch.setattr(recovery, "_start_task", lambda task: task == r"\\Automation\\GitHubRunner")

    evidence = recovery.execute(start=True)

    assert evidence["status"] == "ready"
    assert evidence["runner_started"] is True
    assert evidence["start_method"] == "scheduled_task"
    assert evidence["listener_processes_after"][0]["pid"] == 4242
