from datetime import UTC, datetime

from fastapi import APIRouter, Header

from app.core.correlation import resolver_correlation_id
from app.core.envelope import ok
from app.services.ari_runtime_sql_adapter import AriRuntimeSqlAdapter
from app.services.ari_staging_validator import AriStagingValidator

router = APIRouter(tags=['Analytics Runtime Intelligence'])


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


def _validacoes_base():
    return [
        _item_validacao(
            'COUNT_BEFORE_AFTER',
            'Comparar totais antes/depois',
            'Volume',
            96,
            'Regra de checkpoint de contagem implementada no adapter estático.',
            'Conectar baseline real por domínio antes de usar como evidência de produção.',
            status='warn',
        ),
        _item_validacao(
            'STAT_EXTREMES',
            'Validar extremos e médias',
            'Estatística',
            80,
            'Contrato definido; métricas reais ainda dependem de fonte externa.',
            'Coletar MIN/MAX/AVG da fonte governada.',
            status='warn',
        ),
        _item_validacao(
            'FILTER_ISOLATION',
            'Testar filtros separadamente',
            'Query Intelligence',
            90,
            'Validação sintática de WHERE disponível no adapter.',
            'Persistir impacto real por filtro quando houver fonte conectada.',
            status='warn',
        ),
        _item_validacao(
            'JOIN_CARDINALITY',
            'Validar JOINs utilizados',
            'Relacionamento',
            85,
            'Contagem de JOINs e bloqueio de excesso implementados estaticamente.',
            'Medir cardinalidade real em ambiente controlado.',
            status='warn',
        ),
        _item_validacao(
            'NULL_CRITICAL',
            'Procurar nulos indevidos',
            'Data Quality',
            90,
            'Contrato de null crítico implementado.',
            'Conectar catálogo real de obrigatoriedade.',
            status='warn',
        ),
        _item_validacao(
            'RECONCILIATION',
            'Comparar com fonte oficial',
            'Reconciliação',
            60,
            'Contrato previsto, sem fonte oficial conectada neste snapshot.',
            'Conectar fonte oficial e registrar evidência por execução.',
            status='warn',
        ),
        _item_validacao(
            'GROUP_BY_GRANULARITY',
            'Revisar agregações',
            'Granularidade',
            90,
            'GROUP BY é identificado estaticamente.',
            'Validar granularidade contra dados reais.',
            status='warn',
        ),
        _item_validacao(
            'SAMPLE_INSPECTION',
            'Analisar amostras manuais',
            'Evidência',
            60,
            'Sem golden sample runtime anexado ao snapshot atual.',
            'Anexar amostra governada sem dados sensíveis.',
            status='warn',
        ),
        _item_validacao(
            'BUSINESS_RULES',
            'Revisar regra de negócio aplicada',
            'Governança funcional',
            75,
            'Rastreabilidade documental disponível.',
            'Vincular requisito e evidência de dados reais.',
            status='warn',
        ),
        _item_validacao(
            'AI_GROUNDING',
            'IA governada com fonte e lineage',
            'IA Auditável',
            55,
            'Sem grounding externo ou lineage real neste snapshot.',
            'Bloquear promoção até fonte e lineage reais estarem evidenciados.',
            status='block',
        ),
    ]


def _runtime_sql_validation():
    sample_sql = 'select count(*) as total, status from requisitos where status is not null group by status'
    return AriRuntimeSqlAdapter().validate(
        sample_sql,
        null_critical=0,
        source_name='ari-repository-contract-sample',
    )


def _staging_validation():
    # Fail-closed: ausência de URL/screenshot/smoke externo não vira evidência positiva.
    return AriStagingValidator().validate()


def _telemetry_validation():
    return {
        'telemetry_ready': False,
        'contract_ready': True,
        'correlation_id_supported': True,
        'evidence': 'Contrato de correlação/telemetria existe; exportação OpenTelemetry externa não foi comprovada neste snapshot.',
    }


def _lineage_validation():
    return {
        'lineage_ready': False,
        'contract_ready': True,
        'source': 'ari-repository-contract-sample',
        'flow': ['query', 'runtime_sql_adapter', 'validation_engine', 'readiness_layer'],
        'evidence': 'Lineage lógico do contrato está versionado; lineage de fonte real não está evidenciado.',
    }


def _figma_validation():
    return {
        'status': 'evidence_pending',
        'ready': False,
        'route': '/figma-github',
        'evidence': 'A integração Figma/GitHub existe como superfície separada; nenhum artefato Figma atual é promovido como evidência deste snapshot.',
    }


def _readiness_matrix(runtime_sql, staging, telemetry, lineage, figma):
    return [
        _item_readiness(
            'Backend ARI',
            'IMPLEMENTADO',
            'Endpoint e contrato backend versionados.',
            'CI do HEAD atual deve permanecer verde.',
            'verde',
        ),
        _item_readiness(
            'Frontend ARI',
            'IMPLEMENTADO',
            'Rota e tela integradas ao catálogo atual.',
            'Validação externa de ambiente permanece necessária.',
            'verde',
        ),
        _item_readiness(
            'Runtime SQL Adapter',
            'PARCIAL',
            f"Score estático: {runtime_sql['runtime_sql_score']}%.",
            'Validação atual é sintática e não constitui evidência de banco produtivo.',
            'amarelo',
            True,
        ),
        _item_readiness(
            'Staging Validation',
            'VALIDADO' if staging['staging_ready'] else 'EVIDENCIA_AUSENTE',
            'Evidência externa de staging validada.' if staging['staging_ready'] else 'Sem conjunto completo de URL externa, screenshot e smoke.',
            'Executar staging externo governado.',
            'verde' if staging['staging_ready'] else 'vermelho',
            not staging['staging_ready'],
        ),
        _item_readiness(
            'Telemetry',
            'VALIDADO' if telemetry['telemetry_ready'] else 'PARCIAL',
            telemetry['evidence'],
            'Comprovar exportador e recebimento de telemetria externa.',
            'verde' if telemetry['telemetry_ready'] else 'amarelo',
            not telemetry['telemetry_ready'],
        ),
        _item_readiness(
            'Lineage',
            'VALIDADO' if lineage['lineage_ready'] else 'PARCIAL',
            lineage['evidence'],
            'Conectar lineage a fonte oficial e execução real.',
            'verde' if lineage['lineage_ready'] else 'amarelo',
            not lineage['lineage_ready'],
        ),
        _item_readiness(
            'Figma Runtime',
            'VALIDADO' if figma['ready'] else 'EVIDENCIA_AUSENTE',
            figma['evidence'],
            'Registrar artefato Figma atual somente quando houver readback verificável.',
            'verde' if figma['ready'] else 'cinza',
            False,
        ),
        _item_readiness(
            'Production Readiness',
            'BLOQUEIO',
            'Production readiness é derivado apenas de evidências externas reais; o contrato de repositório sozinho é insuficiente.',
            'Fechar todos os blockers externos antes de promoção.',
            'vermelho',
            True,
        ),
    ]


def _calcular_health_score(validacoes):
    if not validacoes:
        return 0
    return round(sum(item['score'] for item in validacoes) / len(validacoes))


def _snapshot_ari(correlation_id: str):
    validacoes = _validacoes_base()
    runtime_sql = _runtime_sql_validation()
    staging = _staging_validation()
    telemetry = _telemetry_validation()
    lineage = _lineage_validation()
    figma = _figma_validation()
    readiness = _readiness_matrix(runtime_sql, staging, telemetry, lineage, figma)
    blockers = [item for item in readiness if item['bloqueia_producao']]

    return {
        'schema_version': '1.0.0',
        'capability': 'Analytics Runtime Intelligence',
        'evidence_scope': 'repository_contract',
        'correlation_id': correlation_id,
        'health_score': _calcular_health_score(validacoes),
        'production_ready': len(blockers) == 0,
        'draft_recomendado': len(blockers) > 0,
        'atualizado_em': datetime.now(UTC).isoformat(),
        'validacoes': validacoes,
        'runtime_sql_validation': runtime_sql,
        'staging_validation': staging,
        'telemetry_validation': telemetry,
        'lineage_validation': lineage,
        'readiness_matrix': readiness,
        'production_gaps': [item['gap'] for item in blockers],
        'guard_rails': [
            {'regra': 'JOIN explosion', 'acao': 'FAIL'},
            {'regra': 'NULL crítico', 'acao': 'FAIL'},
            {'regra': 'IA sem fonte ou grounding', 'acao': 'BLOCK'},
            {'regra': 'Lineage real ausente', 'acao': 'BLOCK'},
            {'regra': 'Evidência externa ausente', 'acao': 'BLOCK'},
            {'regra': 'PII/log sensível exposto', 'acao': 'FAIL'},
        ],
        'figma': figma,
    }


@router.get('/api/analytics-runtime-intelligence/snapshot')
@router.get('/v1/analytics-runtime-intelligence/snapshot', include_in_schema=False)
def obter_snapshot_ari(
    x_correlation_id: str | None = Header(default=None, alias='X-Correlation-ID'),
    x_request_id: str | None = Header(default=None, alias='X-Request-ID'),
):
    correlation_id = resolver_correlation_id(x_correlation_id, x_request_id)
    return ok(_snapshot_ari(correlation_id), correlation_id)
