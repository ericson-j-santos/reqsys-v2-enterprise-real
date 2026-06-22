from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.envelope import ok

router = APIRouter(prefix='/v1/analytics-runtime-intelligence', tags=['Analytics Runtime Intelligence'])


def _item_validacao(codigo, nome, categoria, score, evidencia, acao_recomendada, status='ok'):
    return {
        'codigo': codigo,
        'nome': nome,
        'categoria': categoria,
        'status': status,
        'score': score,
        'evidencia': evidencia,
        'acao_recomendada': acao_recomendada,
    }


def _item_readiness(capability, estado, evidencia, gap, cor, bloqueia_producao=False):
    return {
        'capability': capability,
        'estado': estado,
        'evidencia': evidencia,
        'gap': gap,
        'cor': cor,
        'bloqueia_producao': bloqueia_producao,
    }


def _item_timeline(evento, estado, detalhe, cor):
    return {'evento': evento, 'estado': estado, 'detalhe': detalhe, 'cor': cor}


def _validacoes_base():
    return [
        _item_validacao('COUNT_BEFORE_AFTER', 'Comparar totais antes/depois', 'Volume', 96, 'Checkpoint de contagem habilitado para origem, staging e destino.', 'Manter limite de divergencia parametrizado por dominio.'),
        _item_validacao('STAT_EXTREMES', 'Validar extremos e medias', 'Estatistica', 88, 'MIN, MAX e AVG consolidados no runtime; thresholds dinamicos pendentes por dominio.', 'Versionar limites de anomalia por indicador critico.', status='warn'),
        _item_validacao('FILTER_ISOLATION', 'Testar filtros separadamente', 'Query Intelligence', 93, 'Fluxo incremental de filtros definido para troubleshooting analitico.', 'Persistir impacto percentual por filtro.'),
        _item_validacao('JOIN_CARDINALITY', 'Validar JOINs utilizados', 'Relacionamento', 87, 'Validador de cardinalidade especificado; controle de explosao cartesiana definido como gate.', 'Coletar baseline real por consulta produtiva.', status='warn'),
        _item_validacao('NULL_CRITICAL', 'Procurar nulos indevidos', 'Data Quality', 95, 'Classificacao de null critico, esperado e operacional definida.', 'Conectar catalogo de campos obrigatorios.'),
        _item_validacao('RECONCILIATION', 'Comparar com fonte oficial', 'Reconciliacao', 90, 'Motor de reconciliacao cross-source definido para SQL, API, DW e RAG.', 'Adicionar adapters reais por fonte oficial.'),
        _item_validacao('GROUP_BY_GRANULARITY', 'Revisar agregacoes', 'Granularidade', 92, 'Validacao de GROUP BY e granularidade incluida no checklist operacional.', 'Exibir dimensoes efetivas no analitico da query.'),
        _item_validacao('SAMPLE_INSPECTION', 'Analisar amostras manuais', 'Evidencia', 91, 'Golden samples previstos para auditoria e reproducibilidade.', 'Criar biblioteca de casos canonicos.'),
        _item_validacao('BUSINESS_RULES', 'Revisar regra de negocio aplicada', 'Governanca funcional', 94, 'Regra de negocio passa a ser evidencia obrigatoria do resultado analitico.', 'Vincular requisito, ADR, teste e query.'),
        _item_validacao('AI_GROUNDING', 'IA governada com fonte e lineage', 'IA Auditavel', 89, 'Resposta sem fonte ou sem grounding definida como BLOCK.', 'Aplicar policy runtime nas respostas de IA.', status='warn'),
    ]


def _readiness_matrix():
    return [
        _item_readiness('Backend ARI', 'VALIDADO', 'Endpoint snapshot e testes backend verdes.', 'Conectar adapter real por fonte.', 'verde'),
        _item_readiness('Frontend ARI', 'VALIDADO', 'Tela navegavel e teste smoke frontend.', 'Validar em staging publicado.', 'verde'),
        _item_readiness('CI/CD', 'VALIDADO', 'Workflows principais verdes no PR.', 'Executar smoke deploy.', 'verde'),
        _item_readiness('Confidence Engine', 'PARCIAL', 'Score consolidado no runtime.', 'Persistir score por execucao real.', 'amarelo'),
        _item_readiness('Explainability', 'PARCIAL', 'Regras e evidencias exibidas em tela.', 'Adicionar lineage real por query.', 'amarelo'),
        _item_readiness('Figma Runtime', 'PARCIAL', 'Bloco visual Figma/GitHub no ARI Center.', 'Materializar artefato Figma quando o plano estiver resolvido.', 'amarelo'),
        _item_readiness('Runtime SQL Adapter', 'PENDENTE', 'Contrato operacional definido.', 'Implementar adapter operacional real.', 'azul', bloqueia_producao=True),
        _item_readiness('Telemetria distribuida', 'PENDENTE', 'Correlation_id previsto.', 'Conectar OpenTelemetry/traces reais.', 'azul', bloqueia_producao=True),
        _item_readiness('Staging Evidence', 'EVIDENCIA AUSENTE', 'CI verde.', 'Validar tela em ambiente publicado e anexar evidencia.', 'cinza', bloqueia_producao=True),
        _item_readiness('Production Readiness', 'BLOQUEIO', 'Ainda sem runtime staging validado.', 'Manter PR em draft ate evidencia operacional.', 'vermelho', bloqueia_producao=True),
    ]


def _production_gaps():
    return [
        'Validar ARI Center em staging publicado.',
        'Capturar evidencia visual da tela operacional.',
        'Implementar Runtime SQL Adapter real.',
        'Conectar telemetria distribuida.',
        'Adicionar lineage real por query/fonte.',
        'Executar smoke deploy.',
        'Materializar artefato Figma quando o plano estiver resolvido.',
    ]


def _runtime_timeline():
    return [
        _item_timeline('Backend ARI criado', 'VALIDADO', 'Endpoint e contrato entregues.', 'verde'),
        _item_timeline('Frontend ARI criado', 'VALIDADO', 'Tela e menu entregues.', 'verde'),
        _item_timeline('CI verde', 'VALIDADO', 'Pipelines principais aprovados.', 'verde'),
        _item_timeline('Readiness Layer', 'IMPLEMENTADO', 'Matriz, gaps e timeline em tela.', 'verde'),
        _item_timeline('Staging validado', 'EVIDENCIA AUSENTE', 'Aguardando ambiente publicado.', 'cinza'),
        _item_timeline('Runtime real', 'PENDENTE', 'Aguardando adapters e telemetria.', 'azul'),
    ]


def _calcular_health_score(validacoes):
    if not validacoes:
        return 0
    return round(sum(item['score'] for item in validacoes) / len(validacoes))


def _snapshot_ari():
    validacoes = _validacoes_base()
    readiness = _readiness_matrix()
    bloqueios = [item for item in readiness if item['bloqueia_producao']]
    return {
        'capability': 'Analytics Runtime Intelligence',
        'posicao_estrategica': 'Plataforma enterprise de inteligencia operacional auditavel',
        'health_score': _calcular_health_score(validacoes),
        'confidence_score': 92,
        'ai_governance_score': 89,
        'operational_quality_score': 91,
        'production_ready': len(bloqueios) == 0,
        'draft_recomendado': len(bloqueios) > 0,
        'ambiente': 'runtime governado',
        'atualizado_em': datetime.now(UTC).isoformat(),
        'validacoes': validacoes,
        'readiness_matrix': readiness,
        'production_gaps': _production_gaps(),
        'runtime_timeline': _runtime_timeline(),
        'guard_rails': [
            {'regra': 'JOIN explosion', 'acao': 'FAIL'},
            {'regra': 'NULL critico', 'acao': 'FAIL'},
            {'regra': 'Divergencia acima do threshold', 'acao': 'FAIL'},
            {'regra': 'IA sem fonte ou sem grounding', 'acao': 'BLOCK'},
            {'regra': 'Lineage ausente', 'acao': 'WARN'},
            {'regra': 'PII/log sensivel exposto', 'acao': 'FAIL'},
        ],
        'figma': {
            'status': 'aguardando_plano_figma',
            'objetivo': 'retorno visual em tela para ARI, Figma e GitHub',
            'artefato': 'Enterprise Operations Center / Analytics Runtime Intelligence',
        },
        'proximas_acoes': [
            'Conectar validadores reais de SQL por adapter.',
            'Persistir historico de health score por execucao.',
            'Adicionar drill-down por query, fonte, regra e incidente.',
            'Sincronizar o artefato Figma com o painel em tela e PR.',
        ],
    }


@router.get('/snapshot')
def obter_snapshot_ari():
    return ok(_snapshot_ari())
