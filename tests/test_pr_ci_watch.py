from scripts.pr_ci_watch import WorkflowRun, classify


def run(status: str, conclusion: str | None, name: str = "CI") -> WorkflowRun:
    return WorkflowRun(
        id=1,
        name=name,
        status=status,
        conclusion=conclusion,
        html_url="https://example.local/run/1",
    )


def test_classify_without_runs_requires_evidence() -> None:
    summary = classify([])

    assert summary["severity"] == "warning"
    assert summary["decision"] == "sem_evidencia_ci_para_o_sha"
    assert summary["score"] == 0.0


def test_classify_success_ready_for_review() -> None:
    summary = classify([run("completed", "success")])

    assert summary["severity"] == "ok"
    assert summary["decision"] == "pronto_para_revisao"
    assert summary["score"] == 100.0


def test_classify_failure_blocks_review() -> None:
    summary = classify([run("completed", "success"), run("completed", "failure", "Lint")])

    assert summary["severity"] == "critical"
    assert summary["decision"] == "corrigir_falhas_antes_de_liberar_revisao"
    assert summary["unhealthy"] == 1


def test_classify_running_waits_without_failing_watch() -> None:
    summary = classify([run("in_progress", None)])

    assert summary["severity"] == "pending"
    assert summary["decision"] == "aguardar_finalizacao_dos_workflows"
    assert summary["running"] == 1


def test_classify_skipped_is_non_blocking_not_green() -> None:
    summary = classify([run("completed", "skipped")])

    assert summary["severity"] == "warning"
    assert summary["decision"] == "sem_check_bloqueante_conclusivo"
    assert summary["non_blocking"] == 1
    assert summary["score"] == 0.0
