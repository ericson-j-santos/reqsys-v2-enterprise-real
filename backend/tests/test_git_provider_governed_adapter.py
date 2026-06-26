from types import SimpleNamespace

from app.services.git_provider_governed_adapter import gerar_plano_git_governado


def _item(**overrides):
    defaults = {
        'id': 201,
        'codigo': 'AGI-201',
        'tipo': 'story',
        'titulo': 'Criar API backend para evidencias GitOps',
        'descricao': 'Implementar endpoint FastAPI, Pydantic e SQLAlchemy para registrar PR e CI.',
        'criterios_aceite': 'Dado um PR com CI verde, quando registrar evidência, então o resumo deve refletir o status.',
        'repositorio': 'ericson-j-santos/reqsys-v2-enterprise-real',
        'branch': None,
        'prioridade': 'P1',
        'pontos': 5,
        'valor_negocio': 75,
        'score_risco': 30,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_plano_github_gera_issue_labels_branch_pipeline_e_pull_request():
    plan = gerar_plano_git_governado(_item(), 'github')

    assert plan.provider == 'github'
    assert plan.repository == 'ericson-j-santos/reqsys-v2-enterprise-real'
    assert plan.change_kind == 'pull_request'
    assert plan.branch_name.startswith('feature/backend/agi-201-')
    assert 'agile-runtime' in plan.labels
    assert 'multi-ia-router' in plan.labels
    assert plan.pipeline_name == 'backend-ci'
    assert plan.governance_mode == 'plan_only'
    assert plan.requires_human_approval is False
    assert 'AGI-201' in plan.issue_title


def test_plano_gitlab_usa_merge_request():
    plan = gerar_plano_git_governado(_item(), 'gitlab')

    assert plan.provider == 'gitlab'
    assert plan.change_kind == 'merge_request'
    assert 'GitLab' in plan.issue_body


def test_plano_risco_alto_exige_aprovacao_humana():
    plan = gerar_plano_git_governado(
        _item(
            titulo='Corrigir JWT, secrets e CORS em producao',
            descricao='Validar seguranca, token, secret, LGPD e permissao antes do deploy.',
            score_risco=90,
            valor_negocio=95,
        ),
        'github',
    )

    assert plan.risk_level == 'alto'
    assert plan.requires_human_approval is True
    assert plan.governance_mode == 'manual_approval_required'
    assert any('aprovação humana' in action or 'aprovacao humana' in action for action in plan.next_actions)


def test_plano_nao_executa_acao_externa():
    plan = gerar_plano_git_governado(_item(), 'github')

    assert 'não executa ação externa automaticamente' in plan.issue_body or 'nao executa acao externa automaticamente' in plan.issue_body
    assert plan.evidence_title == 'Plano GITHUB governado gerado'
