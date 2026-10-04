from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.pr_ci_watch import (  # noqa: E402
    REQUIRED_WORKFLOWS,
    FailureDetail,
    PRStructure,
    WorkflowRun,
    classify,
    decide_remediation,
    latest_relevant_runs,
    render_structural_sweep_markdown,
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



def structure(
    *,
    number: str = "10",
    mergeable: bool | None = True,
    mergeable_state: str = "clean",
    behind_by: int = 0,
    changed_files: int = 1,
    created_at: str = "2026-01-01T00:00:00Z",
) -> PRStructure:
    return PRStructure(
        number=number,
        html_url=f"https://example.local/pull/{number}",
        created_at=created_at,
        head_sha="a" * 40,
        base_sha="b" * 40,
        mergeable=mergeable,
        mergeable_state=mergeable_state,
        behind_by=behind_by,
        ahead_by=1,
        changed_files=changed_files,
        draft=True,
    )


def test_structural_priority_places_conflict_before_empty_and_behind() -> None:
    items = [
        structure(number="10", behind_by=2),
        structure(number="20", changed_files=0),
        structure(number="30", mergeable=False, mergeable_state="dirty"),
    ]
    ordered = sorted(items, key=lambda item: (item.priority, item.created_at or "", int(item.number)))
    assert [item.structural_state for item in ordered] == ["conflicting", "empty_change", "behind"]


def test_empty_change_is_not_treated_as_clean() -> None:
    assert structure(changed_files=0).structural_state == "empty_change"


def test_behind_with_real_diff_is_safe_candidate() -> None:
    assert structure(behind_by=3, changed_files=2).structural_state == "behind"


def test_unknown_mergeability_fails_closed() -> None:
    assert structure(mergeable=None, mergeable_state="unknown").structural_state == "pending_mergeability"


def test_structural_report_exposes_priority_before_ci() -> None:
    markdown = render_structural_sweep_markdown(
        "owner/repo",
        [structure(number="7", mergeable=False, mergeable_state="dirty")],
        {"pr_number": "7", "expected_head_sha": "a" * 40, "executed": False, "reason": "conflict_requires_objective_reconciliation"},
    )
    assert "fila estrutural" in markdown
    assert "conflicting" in markdown
    assert "conflito → diff vazio → branch atrasada → CI" in markdown
