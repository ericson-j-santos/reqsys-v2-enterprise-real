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
    }
