from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.pr_ci_watch import (  # noqa: E402
    REQUIRED_WORKFLOWS,
    FailureDetail,
    WorkflowRun,
    classify,
    decide_remediation,
    latest_relevant_runs,
)


def run(
    name: str,
    *,
    run_id: int,
    conclusion: str | None = "success",
    status: str = "completed",
    updated_at: str = "2026-08-29T01:00:00Z",
    run_attempt: int = 1,
) -> WorkflowRun:
    return WorkflowRun(
        id=run_id,
        name=name,
        status=status,
        conclusion=conclusion,
        html_url=f"https://example.local/run/{run_id}",
        updated_at=updated_at,
        run_attempt=run_attempt,
    )


def healthy_required_runs() -> list[WorkflowRun]:
    return [
        run(name, run_id=index)
        for index, name in enumerate(REQUIRED_WORKFLOWS, start=10)
    ]


def test_classify_without_runs_requires_required_workflows() -> None:
    summary = classify([])

    assert summary["severity"] == "pending"
    assert summary["decision"] == "aguardar_workflows_obrigatorios"
    assert summary["score"] == 0.0
    assert summary["missing"] == list(REQUIRED_WORKFLOWS)


def test_classify_success_requires_all_required_workflows() -> None:
    summary = classify(healthy_required_runs())

    assert summary["severity"] == "ok"
    assert summary["decision"] == "pronto_para_revisao"
    assert summary["score"] == 100.0


def test_classify_failure_blocks_review() -> None:
    runs = healthy_required_runs()
    runs[0] = run(REQUIRED_WORKFLOWS[0], run_id=99, conclusion="failure")

    summary = classify(runs)

    assert summary["severity"] == "critical"
    assert summary["decision"] == "corrigir_falhas_reais_antes_de_liberar_revisao"
    assert summary["unhealthy"] == 1


def test_classify_running_waits_without_false_ready() -> None:
    runs = healthy_required_runs()
    runs[0] = run(
        REQUIRED_WORKFLOWS[0],
        run_id=99,
        conclusion=None,
        status="in_progress",
    )

    summary = classify(runs)

    assert summary["severity"] == "pending"
    assert summary["decision"] == "aguardar_workflows_obrigatorios"
    assert summary["running"] == 1


def test_latest_relevant_runs_ignores_old_failure_and_watcher_itself() -> None:
    target = REQUIRED_WORKFLOWS[0]
    runs = [
        run(target, run_id=1, conclusion="failure", updated_at="2026-08-29T00:00:00Z"),
        run(target, run_id=2, conclusion="success", updated_at="2026-08-29T01:00:00Z"),
        run("PR CI Watch", run_id=3, conclusion="failure", updated_at="2026-08-29T02:00:00Z"),
    ]

    latest = latest_relevant_runs(runs)

    assert [item.id for item in latest] == [2]


def test_old_failed_attempt_does_not_keep_recovered_pr_red() -> None:
    runs = healthy_required_runs()
    runs.append(
        run(
            REQUIRED_WORKFLOWS[0],
            run_id=1,
            conclusion="failure",
            updated_at="2026-08-28T23:00:00Z",
        )
    )

    summary = classify(runs)

    assert summary["severity"] == "ok"
    assert summary["healthy"] == len(REQUIRED_WORKFLOWS)
    assert summary["score"] == 100.0


def test_dependency_install_failure_can_be_retried_once() -> None:
    target = run(REQUIRED_WORKFLOWS[0], run_id=20, conclusion="failure")
    details = [
        FailureDetail(
            job_name="Frontend fast checks",
            job_url="https://example.local/job/20",
            failed_steps=("Instalar dependencias frontend",),
        )
    ]

    decision = decide_remediation(target, details)

    assert decision["action"] == "rerun_failed_jobs"
    assert decision["failure_kind"] == "transient"


def test_unit_test_failure_requires_objective_fix_without_blind_push() -> None:
    target = run(REQUIRED_WORKFLOWS[0], run_id=21, conclusion="failure")
    details = [
        FailureDetail(
            job_name="Frontend fast checks",
            job_url="https://example.local/job/21",
            failed_steps=("Testes unitarios frontend",),
        )
    ]

    decision = decide_remediation(target, details)

    assert decision["action"] == "escalate"
    assert decision["failure_kind"] == "deterministic"


def test_retry_limit_prevents_remediation_loop() -> None:
    target = run(
        REQUIRED_WORKFLOWS[0],
        run_id=22,
        conclusion="failure",
        run_attempt=2,
    )
    details = [
        FailureDetail(
            job_name="Frontend fast checks",
            job_url=None,
            failed_steps=("Instalar dependencias frontend",),
        )
    ]

    decision = decide_remediation(target, details)

    assert decision["action"] == "escalate"
    assert decision["reason"] == "automatic_retry_limit_reached"


def test_workflow_outside_retry_allowlist_is_never_rerun() -> None:
    target = run("Branch Protection Audit", run_id=23, conclusion="failure")
    details = [
        FailureDetail(
            job_name="Audit",
            job_url=None,
            failed_steps=("Setup Python",),
        )
    ]

    decision = decide_remediation(target, details)

    assert decision["action"] == "escalate"
    assert decision["reason"] == "workflow_not_in_retry_allowlist"
