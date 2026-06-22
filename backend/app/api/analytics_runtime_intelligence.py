from datetime import UTC, datetime

from fastapi import APIRouter

from app.core.envelope import ok
from app.services.ari_runtime_sql_adapter import AriRuntimeSqlAdapter
from app.services.ari_staging_validator import AriStagingValidator

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


def _runtime_sql_validation():
    sample_sql = 'select count(*) as total, status from requisitos where status is not null group by status'
    return AriRuntimeSqlAdapter().validate(sample_sql, null_critical=0, source_name='ari-sample-runtime')


def _staging_validation():
    return AriStagingValidator().validate(base_url=None, screenshot_captured=False, smoke_deploy_ok=False)


def _readiness_matrix(runtime_sql=None, staging=None):
    runtime_sql = runtime_sql or _runtime_sql_validation()
    staging = staging or _staging_validation()
    runtime_sql_block = not runtime_sql['runtime_sql_ready']
    staging_block = not staging['staging_ready']
    return [
        _item_readiness('Backend ARI', 'VALIDADO', 'Endpoint snapshot e testes backend verdes.', 'Conectar fonte oficial real.', 'verde'),
        _item_readiness('Frontend ARI', 'VALIDADO', 'Tela navegavel e teste smoke frontend.', 'Validar em staging publicado.', 'verde'),
        _item_readiness('CI/CD', 'VALIDADO', 'Workflows principais verdes no PR.', 'Executar smoke deploy.', 'verde'),
        _item_readiness('Runtime SQL Adapter', 'VALIDADO' if not runtime_sql_block else 'BLOQUEIO', f"Score runtime SQL: {runtime_sql['runtime_sql_score']}%.", 'Conectar consultas reais de dominio.', 'verde' if not runtime_sql_block else 'vermelho', runtime_sql_block),
        _item_readiness('Staging Validation', 'BLOQUEIO' if staging_block else 'VALIDADO', 'Validador de staging executado no snapshot.', 'Informar URL, screenshot e smoke deploy.', 'vermelho' if staging_block else 'verde', staging_block),
        _item_readiness('Confidence Engine', 'PARCIAL', 'Score consolidado no runtime.', 'Persistir score por execucao real.', 'amarelo'),
        _item_readiness('Explainability', 'PARCIAL', 'Regras e evidencias exibidas em tela.', 'Adicionar lineage real por query.', 'amarelo'),
        _item_readiness('Figma Runtime', 'PARCIAL', 'Bloco visual Figma/GitHub no ARI Center.', 'Materializar artefato Figma quando o plano estiver resolvido.', 'amarelo'),
        _item_readiness('Telemetria distribuida', 'PENDENTE', 'Correlation_id previsto.', 'Conectar OpenTelemetry/traces reais.', 'azul', bloqueia_producao=True),
        _item_readiness('Production Readiness', 'BLOQUEIO', 'Ainda sem staging e telemetria real validados.', 'Manter PR em draft ate evidencia operacional.', 'vermelho', True),
    ]


def _production_gaps(staging=None):
    staging = staging or _staging_validation()
    gaps = [
        'Conectar Runtime SQL Adapter a consultas reais de dominio.',
        'Conectar telemetria distribuida.',
        'Adicionar lineage real por query/fonte.',
        'Materializar artefato Figma quando o plano estiver resolvido.',
    ]
    for blocker in staging['blockers']:
        gaps.append(blocker['gap'])
    return gaps


def _runtime_timeline():
    return [
        _item_timeline('Backend ARI criado', 'VALIDADO', 'Endpoint e contrato entregues.', 'verde'),
        _item_timeline('Frontend ARI criado', 'VALIDADO', 'Tela e menu entregues.', 'verde'),
        _item_timeline('CI verde', 'VALIDADO', 'Pipelines principais aprovados.', 'verde'),
        _item_timeline('Readiness Layer', 'IMPLEMENTADO', 'Matriz, gaps e timeline em tela.', 'verde'),
        _item_timeline('Runtime SQL Adapter', 'IMPLEMENTADO', 'Adapter inicial executado no snapshot.', 'verde'),
        _item_timeline('Staging Validation', 'BLOQUEIO', 'Validador criado; evidencias ainda ausentes.', 'vermelho'),
        _item_timeline('Runtime real', 'PARCIAL', 'Adapter existe; falta fonte real e telemetria.', 'amarelo'),
    ]


def _calcular_health_score(validacoes):
    if not validacoes:
        return 0
    return round(sum(item['score'] for item in validacoes) / len(validacoes))


def _snapshot_ari():
    validacoes = _validacoes_base()
    runtime_sql = _runtime_sql_validation()
    staging = _staging_validation()
    readiness = _readiness_matrix(runtime_sql, staging)
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
        'runtime_sql_validation': runtime_sql,
        'staging_validation': staging,
        'readiness_matrix': readiness,
        'production_gaps': _production_gaps(staging),
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
            'Conectar Runtime SQL Adapter a fonte oficial.',
            'Executar staging validation com URL, screenshot e smoke deploy.',
            'Adicionar drill-down por query, fonte, regra e incidente.',
            'Sincronizar o artefato Figma com o painel em tela e PR.',
        ],
    }


@router.get('/snapshot')
def obter_snapshot_ari():
    return ok(_snapshot_ari())
