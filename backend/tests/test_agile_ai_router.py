from types import SimpleNamespace

from app.services.agile_ai_router import recomendar_roteamento_multi_ia


def _item(**overrides):
    defaults = {
        'id': 101,
        'codigo': 'AGI-101',
        'tipo': 'story',
        'titulo': 'Criar endpoint FastAPI para rastreabilidade CI',
        'descricao': 'Implementar API backend com schema Pydantic, SQLAlchemy e workflow de CI.',
        'criterios_aceite': 'Dado um PR com CI verde, entao a evidencia deve ser registrada.',
        'repositorio': 'ericson-j-santos/reqsys-v2-enterprise-real',
        'branch': None,
        'prioridade': 'P2',
        'pontos': 5,
        'valor_negocio': 60,
        'score_risco': 20,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_router_classifica_backend_com_branch_pipeline_e_labels():
    recomendacao = recomendar_roteamento_multi_ia(_item())

    assert recomendacao.owner_ai == 'backend-ia'
    assert recomendacao.categoria == 'backend-api'
    assert recomendacao.pipeline_sugerido == 'backend-ci'
    assert recomendacao.branch_sugerida.startswith('feature/backend/agi-101-')
    assert 'ai:backend-ia' in recomendacao.labels
    assert 'multi-ia-router' in recomendacao.labels
    assert recomendacao.confianca >= 0.5


def test_router_prioriza_devops_quando_ci_cd_predomina():
    recomendacao = recomendar_roteamento_multi_ia(
        _item(
            titulo='Corrigir pipeline GitHub Actions e deploy Fly',
            descricao='Falha no workflow de CI/CD, action e deploy docker.',
            score_risco=55,
            valor_negocio=75,
        )
    )

    assert recomendacao.owner_ai == 'devops-ia'
    assert recomendacao.pipeline_sugerido == 'ci-cd-pipeline'
    assert recomendacao.prioridade_sugerida == 'P1'
    assert 'categoria:devops-ci-cd' in recomendacao.labels


def test_router_eleva_segurança_e_exige_revisao_humana_em_risco_alto():
    recomendacao = recomendar_roteamento_multi_ia(
        _item(
            titulo='Revisar JWT, CORS e secrets de producao',
            descricao='Validar seguranca, permissao, token e LGPD antes do deploy.',
            prioridade='P2',
            score_risco=90,
            valor_negocio=95,
        )
    )

    assert recomendacao.owner_ai == 'security-ia'
    assert recomendacao.prioridade_sugerida == 'P0'
    assert 'risco:alto' in recomendacao.labels
    assert any('revisão humana' in acao or 'revisao humana' in acao for acao in recomendacao.acoes_recomendadas)


def test_router_respeita_branch_existente():
    recomendacao = recomendar_roteamento_multi_ia(
        _item(branch='feature/manual/branch-ja-definida')
    )

    assert recomendacao.branch_sugerida == 'feature/manual/branch-ja-definida'
