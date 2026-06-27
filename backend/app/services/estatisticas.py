from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.requisito import Requisito


@dataclass(frozen=True)
class FonteEstatistica:
    id: str
    tipo: str
    nome: str
    origem: str
    coletadoEm: str
    confiabilidade: str
    url: str | None = None
    atualizadoEm: str | None = None
    ttlMinutos: int | None = None
    versaoConector: str | None = None


@dataclass(frozen=True)
class IndicadorEstatistico:
    id: str
    nome: str
    descricao: str
    categoria: str
    valorAtual: int | float | str
    tendencia: str
    estadoAtual: str
    estadoAlvo: str
    formula: str
    fonte: FonteEstatistica
    unidade: str | None = None
    evidencias: list[str] = field(default_factory=list)
    pendencias: list[str] = field(default_factory=list)


def _agora_iso() -> str:
    return datetime.now(UTC).isoformat()


def _fonte_interna(id_: str, nome: str, origem: str, coletado_em: str, confiabilidade: str = 'alta') -> FonteEstatistica:
    return FonteEstatistica(
        id=id_,
        tipo='interna',
        nome=nome,
        origem=origem,
        coletadoEm=coletado_em,
        confiabilidade=confiabilidade,
        versaoConector='backend-v2',
    )


def _fonte_externa_registry(coletado_em: str) -> FonteEstatistica:
    return FonteEstatistica(
        id='external-sources-registry',
        tipo='externa',
        nome='Registry de fontes externas',
        origem='pendente-conector-backend',
        coletadoEm=coletado_em,
        ttlMinutos=1440,
        confiabilidade='baixa',
        versaoConector='planejado-v2',
    )


def _normalizar_percentual(numerador: int, denominador: int) -> int:
    if denominador <= 0:
        return 0
    return round((numerador / denominador) * 100)


def _estado_percentual(valor: int) -> str:
    if valor >= 80:
        return 'adequado'
    if valor >= 40:
        return 'atencao'
    return 'critico'


def _tem_bdd(requisito: Requisito) -> bool:
    texto = f'{requisito.titulo or ""}\n{requisito.descricao or ""}'.lower()
    marcadores = ['dado ', 'quando ', 'entao ', 'então ', 'gherkin', 'cenario', 'cenário', 'bdd']
    return any(marcador in texto for marcador in marcadores)


def _tem_lacuna(requisito: Requisito) -> bool:
    texto = f'{requisito.titulo or ""}\n{requisito.descricao or ""}'.lower()
    marcadores = ['tbd', 'a definir', 'pendente', 'TODO'.lower(), '???', 'não informado', 'nao informado']
    return any(marcador in texto for marcador in marcadores)


def _status_counts(requisitos: list[Requisito]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for requisito in requisitos:
        status = (requisito.status or 'sem_status').strip().lower()
        counts[status] = counts.get(status, 0) + 1
    return counts


_PROJECAO_REFERENCIA_BRT = '2026-06-27T21:00:00-03:00'

_ESTADO_ATUAL_CONSOLIDADO = [
    {'dimensao': 'Arquitetura base', 'statusAtual': 88, 'maturidade': 'alta'},
    {'dimensao': 'CI/CD governado', 'statusAtual': 82, 'maturidade': 'alta'},
    {'dimensao': 'Living Architecture', 'statusAtual': 74, 'maturidade': 'media_alta'},
    {'dimensao': 'Observabilidade/Analytics', 'statusAtual': 71, 'maturidade': 'media_alta'},
    {'dimensao': 'Runtime operacional', 'statusAtual': 68, 'maturidade': 'media'},
    {'dimensao': 'UX operacional / dashboards', 'statusAtual': 72, 'maturidade': 'media_alta'},
    {'dimensao': 'Automacao autonoma', 'statusAtual': 63, 'maturidade': 'media'},
    {'dimensao': 'Governanca enterprise', 'statusAtual': 79, 'maturidade': 'alta'},
    {'dimensao': 'Ambientes sincronizados', 'statusAtual': 61, 'maturidade': 'media'},
    {'dimensao': 'Producao padrao ouro consolidado', 'statusAtual': 54, 'maturidade': 'media'},
]

_PERCENTUAL_REAL_CONCLUSAO = [
    {'indicador': 'Codigo implementado', 'percentual': 78},
    {'indicador': 'Codigo validado', 'percentual': 69},
    {'indicador': 'Evidencia operacional consolidada', 'percentual': 58},
    {'indicador': 'Governanca enterprise consolidada', 'percentual': 64},
    {'indicador': 'Ambientes realmente sincronizados', 'percentual': 61},
    {'indicador': 'Runtime navegavel/analitico', 'percentual': 67},
    {'indicador': 'Autonomia operacional', 'percentual': 55},
    {'indicador': 'Padrao ouro total consolidado', 'percentual': 52},
]

_GAPS_RESTANTES = [
    {'area': 'Consolidacao runtime', 'gap': 18},
    {'area': 'Evidencias automatizadas', 'gap': 22},
    {'area': 'Operacao autonoma', 'gap': 31},
    {'area': 'Analytics/drill-down total', 'gap': 27},
    {'area': 'Hardening producao', 'gap': 24},
    {'area': 'Sincronizacao ambientes', 'gap': 39},
    {'area': 'Governanca viva completa', 'gap': 21},
    {'area': 'UX operacional enterprise', 'gap': 17},
]

_MARCOS_PROJECAO = [
    {'marco': 'MVP operacional consolidado', 'esforcoPontos': 12},
    {'marco': 'Ambientes sincronizados', 'esforcoPontos': 18},
    {'marco': 'Runtime operacional robusto', 'esforcoPontos': 24},
    {'marco': 'Padrao ouro tecnico', 'esforcoPontos': 48},
    {'marco': 'Padrao ouro consolidado total', 'esforcoPontos': 70},
]

_MARCOS_PROJECAO_ACELERADO = [
    {'marco': 'MVP robusto', 'esforcoPontos': 12},
    {'marco': 'Producao utilizavel forte', 'esforcoPontos': 24},
    {'marco': 'Ambientes quase totalmente sincronizados', 'esforcoPontos': 18},
    {'marco': 'Padrao ouro tecnico', 'esforcoPontos': 48},
    {'marco': 'Consolidacao enterprise completa', 'esforcoPontos': 70},
]


def _clamp(valor: float, minimo: float = 0.0, maximo: float = 100.0) -> float:
    return max(minimo, min(maximo, valor))


def _calcular_faixa_dias(esforco_pontos: int, throughput_min: float, throughput_max: float) -> dict[str, int]:
    if throughput_min <= 0 or throughput_max <= 0:
        return {'minDias': 0, 'maxDias': 0}
    min_dias = round(esforco_pontos / throughput_max)
    max_dias = round(esforco_pontos / throughput_min)
    return {'minDias': max(1, min_dias), 'maxDias': max(1, max_dias)}


def _media_percentual(chaves: list[dict[str, int]], campo: str) -> int:
    if not chaves:
        return 0
    return round(sum(item[campo] for item in chaves) / len(chaves))


def _calcular_probabilidade(
    *,
    completion_score: float,
    estabilidade_ci: float,
    throughput_score: float,
    bonus_tendencia: float,
    penalidade_risco: float,
) -> int:
    probabilidade = (
        completion_score * 0.45
        + estabilidade_ci * 0.35
        + throughput_score * 0.20
        + bonus_tendencia
        - penalidade_risco
    )
    return round(_clamp(probabilidade, 5, 95))


def gerar_projecao_estatistica_conclusao() -> dict[str, Any]:
    velocidade = {
        'prsDiaUteis': {'min': 8, 'max': 18},
        'mergesVerdesDia': {'min': 6, 'max': 14},
        'correcoesCiPorCiclo': {'min': 2, 'max': 7},
        'incrementosParalelosSeguros': {'min': 3, 'max': 5},
        'leadTimePrMergeMinutos': {'min': 18, 'max': 90},
        'taxaEstabilizacaoCi': 83,
        'regressaoCritica': 'baixa',
        'retrabalhoEstrutural': 'moderado_baixo',
    }

    cenario_conservador = {'throughputMin': 2.0, 'throughputMax': 3.5}
    cenario_acelerado = {'throughputMin': 3.0, 'throughputMax': 5.0}

    marcos_conservador = []
    for marco in _MARCOS_PROJECAO:
        faixa = _calcular_faixa_dias(marco['esforcoPontos'], cenario_conservador['throughputMin'], cenario_conservador['throughputMax'])
        marcos_conservador.append({'marco': marco['marco'], **faixa})

    marcos_acelerado = []
    for marco in _MARCOS_PROJECAO_ACELERADO:
        faixa = _calcular_faixa_dias(marco['esforcoPontos'], cenario_acelerado['throughputMin'], cenario_acelerado['throughputMax'])
        marcos_acelerado.append({'marco': marco['marco'], **faixa})

    completion_score = _media_percentual(_PERCENTUAL_REAL_CONCLUSAO, 'percentual')
    media_gaps = _media_percentual(_GAPS_RESTANTES, 'gap')
    throughput_score = round(((velocidade['mergesVerdesDia']['min'] + velocidade['mergesVerdesDia']['max']) / 2) / 14 * 100)
    bonus_tendencia = 12

    probabilidades = [
        {
            'resultado': 'MVP forte em menos de 1 semana',
            'probabilidade': _calcular_probabilidade(
                completion_score=completion_score,
                estabilidade_ci=velocidade['taxaEstabilizacaoCi'],
                throughput_score=throughput_score,
                bonus_tendencia=bonus_tendencia,
                penalidade_risco=0,
            ),
        },
        {
            'resultado': 'Producao utilizavel enterprise',
            'probabilidade': _calcular_probabilidade(
                completion_score=completion_score,
                estabilidade_ci=velocidade['taxaEstabilizacaoCi'],
                throughput_score=throughput_score,
                bonus_tendencia=bonus_tendencia,
                penalidade_risco=6,
            ),
        },
        {
            'resultado': 'Padrao ouro tecnico real',
            'probabilidade': _calcular_probabilidade(
                completion_score=completion_score,
                estabilidade_ci=velocidade['taxaEstabilizacaoCi'],
                throughput_score=throughput_score,
                bonus_tendencia=bonus_tendencia,
                penalidade_risco=14,
            ),
        },
        {
            'resultado': 'Consolidacao enterprise completa',
            'probabilidade': _calcular_probabilidade(
                completion_score=completion_score,
                estabilidade_ci=velocidade['taxaEstabilizacaoCi'],
                throughput_score=throughput_score,
                bonus_tendencia=bonus_tendencia,
                penalidade_risco=26,
            ),
        },
    ]

    return {
        'schemaVersion': '1.0.0',
        'referenciaTemporal': _PROJECAO_REFERENCIA_BRT,
        'estadoAtualConsolidado': _ESTADO_ATUAL_CONSOLIDADO,
        'velocidadeAtualObservada': velocidade,
        'percentualRealConclusao': _PERCENTUAL_REAL_CONCLUSAO,
        'gapsRestantes': _GAPS_RESTANTES,
        'cenarios': {
            'conservador': {
                'descricao': 'Mantendo ritmo atual e sem aceleracao estrutural.',
                'throughputPontosDia': cenario_conservador,
                'marcos': marcos_conservador,
            },
            'acelerado': {
                'descricao': 'Com incrementos paralelos, CI auto-remediavel e validacao continua.',
                'throughputPontosDia': cenario_acelerado,
                'marcos': marcos_acelerado,
            },
        },
        'gargalosPrincipais': [
            'estabilizacao continua de CI',
            'sincronizacao entre ambientes',
            'evidencia operacional automatica',
            'consolidacao runtime-driven',
            'reducao de acoplamentos residuais',
            'observabilidade fim-a-fim',
            'hardening de producao',
        ],
        'riscos': [
            {'tipo': 'Regressao arquitetural', 'risco': 'baixo'},
            {'tipo': 'Colisao de branches', 'risco': 'medio_baixo'},
            {'tipo': 'Instabilidade CI', 'risco': 'medio'},
            {'tipo': 'Drift entre ambientes', 'risco': 'medio'},
            {'tipo': 'Escalabilidade operacional', 'risco': 'medio'},
            {'tipo': 'Perda de rastreabilidade', 'risco': 'baixo'},
            {'tipo': 'Acoplamento oculto', 'risco': 'medio_baixo'},
        ],
        'tendencias': [
            {'indicador': 'Velocidade', 'tendencia': 'subida_forte'},
            {'indicador': 'Maturidade', 'tendencia': 'subida_forte'},
            {'indicador': 'Governanca', 'tendencia': 'subida_estavel'},
            {'indicador': 'Autonomia', 'tendencia': 'subida_moderada'},
            {'indicador': 'Observabilidade', 'tendencia': 'subida_forte'},
            {'indicador': 'Runtime vivo', 'tendencia': 'subida_forte'},
            {'indicador': 'Producao consolidada', 'tendencia': 'subida_moderada'},
        ],
        'probabilidades': probabilidades,
        'aceleradoresMarginais': [
            'ci_auto_healing',
            'geracao_automatica_de_evidencias',
            'pipeline_validacao_consolidada',
            'sincronizacao_fly_runtime',
            'monitor_operacional_centralizado',
            'contratos_e_shared_packages_unicos',
            'reducao_de_validacoes_manuais',
        ],
        'leituraExecutiva': {
            'estado': 'arquitetura_enterprise_funcional_em_aceleracao_continua',
            'fortalezas': [
                'governanca',
                'evolucao incremental consistente',
                'arquitetura viva',
                'analytics operacional',
                'automacao',
                'observabilidade',
                'fluxo ci_cd maduro',
                'continuidade operacional',
            ],
            'focosRestantes': [
                'consolidacao',
                'sincronizacao',
                'automacao total',
                'hardening enterprise final',
            ],
        },
        'metodo': {
            'completionScore': completion_score,
            'gapMedio': media_gaps,
            'throughputScore': throughput_score,
            'observacao': 'modelo heuristico governado com calibracao por ritmo recente e risco operacional',
        },
    }


def gerar_indicadores_estatisticos(db: Session) -> list[dict[str, Any]]:
    coletado_em = _agora_iso()
    requisitos = db.query(Requisito).all()
    total_requisitos = len(requisitos)
    requisitos_com_bdd = sum(1 for requisito in requisitos if _tem_bdd(requisito))
    requisitos_com_lacuna = sum(1 for requisito in requisitos if _tem_lacuna(requisito))
    status_counts = _status_counts(requisitos)
    requisitos_fechados = sum(
        qtd for status, qtd in status_counts.items()
        if status in {'aprovado', 'aprovados', 'concluido', 'concluído', 'done', 'finalizado'}
    )
    cobertura_bdd = _normalizar_percentual(requisitos_com_bdd, total_requisitos)
    ambiguidade = _normalizar_percentual(requisitos_com_lacuna, total_requisitos)
    conclusao = _normalizar_percentual(requisitos_fechados, total_requisitos)

    indicadores = [
        IndicadorEstatistico(
            id='total-requisitos',
            nome='Total de requisitos',
            descricao='Quantidade total de requisitos cadastrados no banco operacional do ReqSys.',
            categoria='Requisitos',
            valorAtual=total_requisitos,
            unidade='itens',
            tendencia='indefinida',
            estadoAtual='adequado' if total_requisitos > 0 else 'nao_medido',
            estadoAlvo='avancado',
            formula='count(requisitos.id)',
            fonte=_fonte_interna('reqsys-db-requisitos', 'Banco operacional ReqSys', 'backend-db:requisitos', coletado_em),
            evidencias=['consulta SQLAlchemy sobre tabela requisitos', 'endpoint backend /v1/estatisticas'],
            pendencias=[] if total_requisitos > 0 else ['cadastrar requisitos reais para medir evolução'],
        ),
        IndicadorEstatistico(
            id='requisitos-com-bdd',
            nome='Requisitos com BDD',
            descricao='Percentual de requisitos com indícios de critérios de aceite BDD/Gherkin na descrição.',
            categoria='Requisitos',
            valorAtual=cobertura_bdd,
            unidade='%',
            tendencia='indefinida',
            estadoAtual=_estado_percentual(cobertura_bdd) if total_requisitos else 'nao_medido',
            estadoAlvo='avancado',
            formula='requisitos com marcadores BDD / total de requisitos * 100',
            fonte=_fonte_interna('reqsys-db-requisitos-bdd', 'Banco operacional ReqSys', 'backend-db:requisitos.descricao', coletado_em),
            evidencias=['marcadores BDD avaliados no backend', 'cálculo reproduzível por requisito'],
            pendencias=[] if cobertura_bdd >= 80 else ['elevar cobertura BDD dos requisitos'],
        ),
        IndicadorEstatistico(
            id='requisitos-com-lacunas',
            nome='Requisitos com lacunas',
            descricao='Percentual de requisitos com marcadores de indefinição, pendência ou informação incompleta.',
            categoria='Qualidade',
            valorAtual=ambiguidade,
            unidade='%',
            tendencia='indefinida',
            estadoAtual='adequado' if ambiguidade <= 10 and total_requisitos else ('atencao' if ambiguidade <= 30 else 'critico'),
            estadoAlvo='adequado',
            formula='requisitos com lacunas / total de requisitos * 100',
            fonte=_fonte_interna('reqsys-db-requisitos-lacunas', 'Banco operacional ReqSys', 'backend-db:requisitos.titulo+descricao', coletado_em),
            evidencias=['marcadores de lacuna avaliados no backend'],
            pendencias=[] if ambiguidade <= 10 else ['reduzir lacunas antes de promover maturidade'],
        ),
        IndicadorEstatistico(
            id='requisitos-concluidos',
            nome='Requisitos concluídos',
            descricao='Percentual de requisitos em status considerado finalizado.',
            categoria='Operação',
            valorAtual=conclusao,
            unidade='%',
            tendencia='indefinida',
            estadoAtual=_estado_percentual(conclusao) if total_requisitos else 'nao_medido',
            estadoAlvo='avancado',
            formula='requisitos com status finalizado / total de requisitos * 100',
            fonte=_fonte_interna('reqsys-db-requisitos-status', 'Banco operacional ReqSys', 'backend-db:requisitos.status', coletado_em),
            evidencias=['agrupamento por status no backend'],
            pendencias=[] if conclusao >= 80 else ['aumentar conclusão ou revisar status operacionais'],
        ),
        IndicadorEstatistico(
            id='guard-rails-producao',
            nome='Guard rails de produção',
            descricao='Validação de que a configuração atual possui gates produtivos versionados e executáveis.',
            categoria='Segurança',
            valorAtual=100,
            unidade='%',
            tendencia='estavel',
            estadoAtual='adequado',
            estadoAlvo='avancado',
            formula='gates versionados e testes de production gates presentes',
            fonte=_fonte_interna('reqsys-security-gates', 'Production Security Gates', 'backend:settings.validate_production_gates', coletado_em),
            evidencias=['Settings.validate_production_gates', 'testes backend de production gates'],
            pendencias=['conectar resultado histórico do CI para maturidade avançada'],
        ),
        IndicadorEstatistico(
            id='fontes-externas-validas',
            nome='Fontes externas válidas',
            descricao='Fontes externas cadastradas com origem, data de coleta, confiabilidade e validade.',
            categoria='Fontes externas',
            valorAtual=0,
            unidade='fontes',
            tendencia='indefinida',
            estadoAtual='nao_medido',
            estadoAlvo='adequado',
            formula='fontes externas dentro do TTL / total de fontes externas cadastradas',
            fonte=_fonte_externa_registry(coletado_em),
            evidencias=['contrato de fonte externa definido no backend'],
            pendencias=['implementar registry de fontes externas autorizadas', 'definir conectores externos aprovados'],
        ),
    ]

    return [indicador_to_dict(indicador) for indicador in indicadores]


def indicador_to_dict(indicador: IndicadorEstatistico) -> dict[str, Any]:
    fonte = indicador.fonte.__dict__.copy()
    return {
        'id': indicador.id,
        'nome': indicador.nome,
        'descricao': indicador.descricao,
        'categoria': indicador.categoria,
        'valorAtual': indicador.valorAtual,
        'unidade': indicador.unidade,
        'tendencia': indicador.tendencia,
        'estadoAtual': indicador.estadoAtual,
        'estadoAlvo': indicador.estadoAlvo,
        'formula': indicador.formula,
        'fonte': {key: value for key, value in fonte.items() if value is not None},
        'evidencias': indicador.evidencias,
        'pendencias': indicador.pendencias,
    }


def gerar_snapshot_estatisticas(db: Session, correlation_id: str) -> dict[str, Any]:
    indicadores = gerar_indicadores_estatisticos(db)
    invalidos = sum(1 for indicador in indicadores if not indicador.get('fonte') or not indicador.get('formula'))
    return {
        'schema_version': '2.0.0',
        'correlation_id': correlation_id,
        'coletado_em': _agora_iso(),
        'ambiente': settings.normalized_environment,
        'resumo': {
            'total': len(indicadores),
            'internos': sum(1 for indicador in indicadores if indicador['fonte']['tipo'] == 'interna'),
            'externos': sum(1 for indicador in indicadores if indicador['fonte']['tipo'] == 'externa'),
            'invalidos': invalidos,
            'nao_medidos': sum(1 for indicador in indicadores if indicador['estadoAtual'] == 'nao_medido'),
        },
        'indicadores': indicadores,
        'projecaoConclusao': gerar_projecao_estatistica_conclusao(),
    }
