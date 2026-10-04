import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_ci_enterprise_maturity_usa_superficies_canonicas_atuais() -> None:
    fast = read(".github/workflows/ci-enterprise-fast.yml")
    regression = read(".github/workflows/ci-enterprise-regression.yml")
    observability = read(".github/workflows/ci-observability.yml")
    guardrails = read("scripts/ci_enterprise_guardrails.py")

    assert "name: CI Enterprise Fast" in fast
    assert "CI Admission Controller" in fast
    assert "scripts/ci_enterprise_guardrails.py" in fast
    assert 'NODE_VERSION: "20.19.0"' in fast
    assert "Sumario CI Enterprise Fast" in fast

    assert "name: CI Enterprise Regression" in regression
    assert "schedule:" in regression
    assert "workflow_dispatch:" in regression
    assert "ci-enterprise-regression-map" in regression
    assert '"blocking":false' in regression

    assert "name: CI Observability" in observability
    assert "workflow_run:" in observability
    assert "ci-observability-dashboard" in observability

    assert "ci-enterprise-guardrails.json" in guardrails


def test_fast_path_permanece_na_politica_de_merge_do_sha_atual() -> None:
    policy = json.loads(read("governance/merge/current-sha-required-workflows.json"))

    assert "CI Enterprise Fast" in policy["required_workflows"]
    assert "CI — ReqSys v2 Enterprise" in policy["required_workflows"]
    assert "Pre-PR Readiness Gate" in policy["required_workflows"]


def test_observabilidade_historica_nao_reintroduz_workflow_duplicado() -> None:
    assert not (ROOT / ".github/workflows/ci-enterprise-observability.yml").exists()
    assert (ROOT / ".github/workflows/ci-observability.yml").is_file()
