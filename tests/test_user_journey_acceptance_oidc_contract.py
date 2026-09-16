from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/user-journey-acceptance-dev.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_acceptance_dispatch_exige_same_sha():
    text = _workflow()
    assert 'if [ "$source_sha" != "$expected_sha" ]; then' in text
    assert "Same-SHA obrigatório" in text
    assert "exit 42" in text


def test_business_probe_usa_graph_oidc_e_nao_secret():
    text = _workflow()
    assert "Autenticar identidade WSJF por OIDC" in text
    assert "az account get-access-token --resource-type ms-graph" in text
    assert "POWER_PLATFORM_GRAPH_ACCESS_TOKEN=$token" in text
    business = text.split("- name: Produzir evidência real Planner → Power Automate → Excel", 1)[1]
    business = business.split("- name: Validar efeito de negócio real", 1)[0]
    assert "steps.wsjf_graph.outcome == 'success'" in business
    assert "POWER_PLATFORM_CLIENT_SECRET" not in business
