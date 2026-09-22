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
    assert "Autenticar integrações Microsoft por OIDC" in text
    assert "az account get-access-token --resource-type ms-graph" in text
    assert "POWER_PLATFORM_GRAPH_ACCESS_TOKEN=$graph_token" in text
    business = text.split("- name: Produzir evidência real Planner → Power Automate → Excel", 1)[1]
    business = business.split("- name: Validar efeito de negócio real", 1)[0]
    assert "steps.microsoft_integrations.outcome == 'success'" in business
    assert "POWER_PLATFORM_CLIENT_SECRET" not in business


def test_acceptance_usa_runtime_pc24x7_e_bloqueia_fly():
    text = _workflow()
    assert "PC24X7_DEV_BASE_URL" in text
    assert "PC24X7_DEV_FRONTEND_URL" in text
    assert "/api/runtime/health" in text
    assert "Fly.io está descontinuado" in text
    assert "reqsys-api-dev.fly.dev" not in text
    assert "reqsys-app-dev.fly.dev" not in text
    assert "flyctl" not in text
    assert "fly-api-dev-deploy" not in text


def test_integracoes_microsoft_sao_oidc_sem_client_secret():
    text = _workflow()
    assert "Autenticar integrações Microsoft por OIDC" in text
    assert "az account get-access-token --resource-type ms-graph" in text
    assert "az account get-access-token --resource https://api.powerplatform.com/" in text
    assert "powerplatform_environments" in text
    assert "graph_groups" in text
    assert "POWER_PLATFORM_CLIENT_SECRET" not in text
