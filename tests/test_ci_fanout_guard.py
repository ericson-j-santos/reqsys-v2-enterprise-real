from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_workflow(name: str) -> dict:
    data = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    return data


def triggers(data: dict) -> dict:
    # PyYAML 1.1 pode interpretar a chave "on" como True.
    return data.get("on") or data.get(True) or {}


def test_pr_evidence_usa_um_sinal_canonico_e_nao_dispara_na_main() -> None:
    data = load_workflow("pr-evidence-gate.yml")
    workflow_run = triggers(data)["workflow_run"]

    assert workflow_run["workflows"] == ["CI — ReqSys v2 Enterprise"]
    assert workflow_run["branches-ignore"] == ["main"]


def test_pr_ci_watch_nao_cria_workflow_run_para_main() -> None:
    data = load_workflow("pr-ci-watch.yml")
    assert triggers(data)["workflow_run"]["branches-ignore"] == ["main"]


def test_ollama_triage_nao_dispara_na_main_e_deduplica_por_head() -> None:
    data = load_workflow("ollama-ci-triage.yml")
    workflow_run = triggers(data)["workflow_run"]
    concurrency = data["concurrency"]

    assert workflow_run["branches-ignore"] == ["main"]
    assert concurrency["cancel-in-progress"] is True
    assert "workflow_run.head_sha" in concurrency["group"]


def test_ci_observability_deduplica_por_workflow_e_head() -> None:
    data = load_workflow("ci-observability.yml")
    concurrency = data["concurrency"]

    assert concurrency["cancel-in-progress"] is True
    assert "workflow_run.head_sha" in concurrency["group"]
    assert "workflow_run.name" in concurrency["group"]


def test_workflows_alterados_nao_usam_refs_mutaveis_de_actions() -> None:
    mutable = re.compile(r"uses:\\s+actions/[^@\\s]+@v\\d+")
    for name in (
        "pr-evidence-gate.yml",
        "pr-ci-watch.yml",
        "ollama-ci-triage.yml",
        "ci-observability.yml",
    ):
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert mutable.search(text) is None, name
