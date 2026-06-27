from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.requisito import Requisito

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECTION_SOURCE_PATH = _REPO_ROOT / 'docs' / 'analytics' / 'reqsys_projecao_estatistica_conclusao.json'
_PROJECTION_SOURCE_ORIGIN = f'docs:{_PROJECTION_SOURCE_PATH.relative_to(_REPO_ROOT).as_posix()}'
_STATUS_FINAIS = {'aprovado', 'aprovados', 'concluido', 'concluído', 'done', 'finalizado'}


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


def _carregar_projecao_estatistica() -> dict[str, Any]:
    try:
        return json.loads(_PROJECTION_SOURCE_PATH.read_text(encoding='utf-8'))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def _formatar_faixa_dias(faixa: dict[str, int]) -> str:
    minimo = max(int(faixa.get('min', 0)), 0)
    maximo = max(int(faixa.get('max', 0)), 0)
    if minimo and maximo and minimo != maximo:
        return f'{minimo}-{maximo} dias'
    valor = max(minimo, maximo)
    if valor == 1:
        return '1 dia'
    return f'{valor} dias'


def _normalizar_tendencia_exec(percentual: int, tendencia: str | None = None) -> str:
    if tendencia == 'estavel_alta':
        return 'estavel'
    if tendencia in {'forte_alta', 'moderada_alta'}:
        return 'subindo'
    if percentual >= 80:
        return 'estavel'
    if percentual >= 40:
        return 'subindo'
    return 'indefinida'


def _buscar_percentual_por_id(itens: list[dict[str, Any]], item_id: str) -> int:
    for item in itens:
        if item.get('id') == item_id:
            return int(item.get('percentual', 0))
    return 0


def _buscar_probabilidade_por_id(itens: list[dict[str, Any]], item_id: str) -> int:
    for item in itens:
        if item.get('id') == item_id:
            return int(item.get('percentual', 0))
    return 0


def _buscar_marco_por_id(cenario: dict[str, Any], marco_id: str) -> dict[str, Any]:
    for marco in cenario.get('marcos', []):
        if marco.get('id') == marco_id:
            return marco
    return {}


def _normalizar_cenario_projecao(cenario_id: str, nome: str, payload: dict[str, Any]) -> dict[str, Any]:
    marcos = []
    for marco in payload.get('marcos', []):
        faixa = marco.get('dias', {})
        marcos.append(
            {
                'id': marco.get('id'),
                'nome': marco.get('nome'),
                'dias': faixa,
                'faixaDias': _formatar_faixa_dias(faixa),
            }
        )
    return {
        'id': cenario_id,
        'nome': nome,
        'descricao': payload.get('descricao'),
        'marcos': marcos,
    }


def _normalizar_velocidade_atual(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'id': item.get('id'),
            'nome': item.get('nome'),
            'valorTexto': item.get('valor_texto'),
            'unidade': item.get('unidade'),
        }
        for item in itens
    ]


def _normalizar_projecao_conclusao(projecao: dict[str, Any]) -> dict[str, Any] | None:
    if not projecao:
        return None

    estado_atual = projecao.get('estado_atual_consolidado', [])
    percentual_real = projecao.get('percentual_real_conclusao', [])
    probabilidades = projecao.get('probabilidades', [])
    cenarios = projecao.get('projecao_tempo', {})
    cenario_conservador = cenarios.get('conservador', {})
    cenario_acelerado = cenarios.get('acelerado', {})

    maturidade_media = round(sum(int(item.get('percentual', 0)) for item in estado_atual) / len(estado_atual)) if estado_atual else 0
    padrao_ouro_atual = _buscar_percentual_por_id(percentual_real, 'padrao-ouro-consolidado-total')
    probabilidade_mvp_semana = _buscar_probabilidade_por_id(probabilidades, 'mvp-forte-menos-1-semana')
    probabilidade_producao = _buscar_probabilidade_por_id(probabilidades, 'producao-utilizavel-enterprise')
    mvp_conservador = _buscar_marco_por_id(cenario_conservador, 'mvp-operacional-consolidado')
    mvp_acelerado = _buscar_marco_por_id(cenario_acelerado, 'mvp-robusto')

    return {
        'schemaVersion': projecao.get('schema_version', '1.0.0'),
        'referenciaTemporal': projecao.get('referencia_temporal'),
        'origem': _PROJECTION_SOURCE_ORIGIN,
        'resumo': {
            'maturidadeMediaDimensoes': maturidade_media,
            'padraoOuroAtual': padrao_ouro_atual,
            'probabilidadeMvpSemana': probabilidade_mvp_semana,
            'probabilidadeProducaoEnterprise': probabilidade_producao,
            'janelaMvpConservadora': _formatar_faixa_dias(mvp_conservador.get('dias', {})) if mvp_conservador else None,
            'janelaMvpAcelerada': _formatar_faixa_dias(mvp_acelerado.get('dias', {})) if mvp_acelerado else None,
        },
        'estadoAtualConsolidado': estado_atual,
        'velocidadeAtual': _normalizar_velocidade_atual(projecao.get('velocidade_atual', {}).get('cadencia_recente', [])),
        'percentualRealConclusao': percentual_real,
        'gapRestante': projecao.get('gap_restante', []),
        'cenarios': [
            _normalizar_cenario_projecao('conservador', 'Cenario conservador', cenario_conservador),
            _normalizar_cenario_projecao('acelerado', 'Cenario acelerado', cenario_acelerado),
        ],
        'principaisGargalos': projecao.get('gargalos', []),
        'riscos': projecao.get('riscos', []),
        'tendencias': projecao.get('tendencias', []),
        'probabilidades': probabilidades,
        'aceleradores': projecao.get('aceleradores', []),
        'leituraExecutiva': projecao.get('leitura_executiva', {}),
    }


def _gerar_indicadores_projecao_estatistica(coletado_em: str) -> list[IndicadorEstatistico]:
    projecao = _carregar_projecao_estatistica()
    percentual_real = projecao.get('percentual_real_conclusao', [])
    tendencias = {item.get('id'): item.get('tendencia') for item in projecao.get('tendencias', [])}
    pendencias_por_id = {
        'codigo-implementado': ['converter implementacao em validacao operacional reproduzivel'],
        'codigo-validado': ['aumentar cobertura de validacao end-to-end e de CI'],
        'evidencia-operacional-consolidada': ['automatizar coleta e publicacao de evidencias operacionais'],
        'governanca-enterprise-consolidada': ['fechar lacunas de governanca viva e sincronizar checkpoints'],
        'sincronizacao-ambientes': ['reduzir drift entre ambientes e alinhar runtime publicado'],
        'runtime-navegavel-analitico': ['expandir analytics com drill-down e correlacao fim-a-fim'],
        'autonomia-operacional': ['reduzir validacoes manuais e ampliar auto-remediacao'],
        'padrao-ouro-consolidado-total': ['combinar hardening de producao, evidencias e sincronizacao final'],
    }
    metadados = {
        'codigo-implementado': {
            'categoria': 'Entrega',
            'descricao': 'Baseline executivo do percentual de codigo ja entregue no ecossistema ReqSys.',
        },
        'codigo-validado': {
            'categoria': 'Validacao',
            'descricao': 'Parcela do codigo que ja possui validacao consistente e utilizavel para decisoes.',
        },
        'evidencia-operacional-consolidada': {
            'categoria': 'Evidencia operacional',
            'descricao': 'Nivel de evidencias automatizadas e reaproveitaveis para sustentar o runtime.',
        },
        'governanca-enterprise-consolidada': {
            'categoria': 'Governanca',
            'descricao': 'Maturidade executiva consolidada de governanca enterprise no fluxo atual.',
        },
        'sincronizacao-ambientes': {
            'categoria': 'Ambientes',
            'descricao': 'Aderencia entre ambientes e runtime efetivamente sincronizados.',
        },
        'runtime-navegavel-analitico': {
            'categoria': 'Operacao',
            'descricao': 'Maturidade do runtime navegavel, observavel e com analitico operacional.',
        },
        'autonomia-operacional': {
            'categoria': 'Automacao',
            'descricao': 'Capacidade de a operacao evoluir com menor intervencao manual e mais agentes especializados.',
        },
        'padrao-ouro-consolidado-total': {
            'categoria': 'Projeção executiva',
            'descricao': 'Percentual de consolidacao do padrao ouro total estimado na referencia executiva.',
            'estadoAlvo': 'excelencia',
        },
    }

    indicadores: list[IndicadorEstatistico] = []
    for item in percentual_real:
        indicador_id = str(item.get('id'))
        percentual = int(item.get('percentual', 0))
        metadata = metadados.get(indicador_id, {})
        indicadores.append(
            IndicadorEstatistico(
                id=indicador_id,
                nome=str(item.get('nome', indicador_id)),
                descricao=metadata.get(
                    'descricao',
                    f'Percentual executivo consolidado para {str(item.get("nome", indicador_id)).lower()}.',
                ),
                categoria=metadata.get('categoria', 'Projeção executiva'),
                valorAtual=percentual,
                unidade='%',
                tendencia=_normalizar_tendencia_exec(percentual, tendencias.get(indicador_id)),
                estadoAtual=_estado_percentual(percentual),
                estadoAlvo=metadata.get('estadoAlvo', 'avancado'),
                formula='baseline executivo consolidado na referencia temporal',
                fonte=_fonte_interna(
                    'reqsys-projecao-estatistica',
                    'Projecao estatistica versionada',
                    _PROJECTION_SOURCE_ORIGIN,
                    coletado_em,
                    'media',
                ),
                evidencias=[
                    'baseline executivo consolidado por frentes, runtime e governanca',
                    'cadencia recente de PRs, merges e estabilizacao de CI versionada em docs',
                ],
                pendencias=[] if percentual >= 80 else pendencias_por_id.get(indicador_id, ['elevar maturidade estatistica da frente']),
            )
        )
    return indicadores


def gerar_indicadores_estatisticos(db: Session) -> list[dict[str, Any]]:
    coletado_em = _agora_iso()
    requisitos = db.query(Requisito).all()
    total_requisitos = len(requisitos)
    requisitos_com_bdd = sum(1 for requisito in requisitos if _tem_bdd(requisito))
    requisitos_com_lacuna = sum(1 for requisito in requisitos if _tem_lacuna(requisito))
    status_counts = _status_counts(requisitos)
    requisitos_fechados = sum(
        qtd for status, qtd in status_counts.items()
        if status in _STATUS_FINAIS
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
    indicadores.extend(_gerar_indicadores_projecao_estatistica(coletado_em))

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
    projecao_conclusao = _normalizar_projecao_conclusao(_carregar_projecao_estatistica())
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
        'projecaoConclusao': projecao_conclusao,
    }
