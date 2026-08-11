"""Telemetria Pareto para fluxos de fila do ReqSys.

Concentra volume, latência, erros e saturação sem persistir PII.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from statistics import mean
from time import perf_counter
from typing import Final

from sqlalchemy import Column, DateTime, Integer, MetaData, Table, Text, create_engine, select

from app.core.telemetry import log_evento


class EstadoFila(StrEnum):
    DISPONIVEL = 'DISPONIVEL'
    RESERVADA = 'RESERVADA'
    EM_ATENDIMENTO = 'EM_ATENDIMENTO'
    CONCLUIDA = 'CONCLUIDA'


TRANSICOES_PERMITIDAS: Final[dict[EstadoFila, set[EstadoFila]]] = {
    EstadoFila.DISPONIVEL: {EstadoFila.RESERVADA},
    EstadoFila.RESERVADA: {EstadoFila.EM_ATENDIMENTO, EstadoFila.DISPONIVEL},
    EstadoFila.EM_ATENDIMENTO: {EstadoFila.CONCLUIDA, EstadoFila.DISPONIVEL},
    EstadoFila.CONCLUIDA: set(),
}


@dataclass(frozen=True, slots=True)
class TransicaoFila:
    demanda_hash: str
    estado_origem: EstadoFila
    estado_destino: EstadoFila
    correlation_id: str
    duracao_ms: int
    sucesso: bool
    erro_codigo: str | None = None


def anonimizar_demanda_id(demanda_id: str) -> str:
    """Retorna identificador técnico irreversível, adequado para métricas e logs."""
    valor = demanda_id.strip()
    if not valor:
        raise ValueError('demanda_id_obrigatoria')
    return hashlib.sha256(valor.encode('utf-8')).hexdigest()[:16]


class RegistroObservabilidadeFila:
    """Registro em memória, thread-safe e sem cardinalidade por demanda."""

    def __init__(self, limite_amostras: int = 1000) -> None:
        if limite_amostras < 1:
            raise ValueError('limite_amostras_deve_ser_positivo')
        self._limite_amostras = limite_amostras
        self._lock = threading.Lock()
        self._transicoes: Counter[str] = Counter()
        self._erros: Counter[str] = Counter()
        self._estados: Counter[str] = Counter()
        self._duracoes_ms: list[int] = []

    def registrar(self, evento: TransicaoFila) -> None:
        if evento.estado_destino not in TRANSICOES_PERMITIDAS[evento.estado_origem]:
            raise ValueError(
                f'transicao_invalida:{evento.estado_origem.value}->{evento.estado_destino.value}'
            )
        chave = f'{evento.estado_origem.value}->{evento.estado_destino.value}'
        with self._lock:
            self._transicoes[chave] += 1
            self._estados[evento.estado_destino.value] += 1
            if evento.sucesso:
                self._estados[evento.estado_origem.value] = max(
                    0, self._estados[evento.estado_origem.value] - 1
                )
            else:
                self._erros[evento.erro_codigo or 'ERRO_NAO_CLASSIFICADO'] += 1
            self._duracoes_ms.append(max(0, evento.duracao_ms))
            self._duracoes_ms = self._duracoes_ms[-self._limite_amostras :]

        log_evento(
            'fila.transicao',
            demanda_hash=evento.demanda_hash,
            estado_origem=evento.estado_origem.value,
            estado_destino=evento.estado_destino.value,
            correlation_id=evento.correlation_id,
            duracao_ms=evento.duracao_ms,
            sucesso=evento.sucesso,
            erro_codigo=evento.erro_codigo,
        )

    def snapshot(self) -> dict:
        with self._lock:
            duracoes = sorted(self._duracoes_ms)
            total = sum(self._transicoes.values())
            erros = sum(self._erros.values())
            p95_indice = max(0, round(0.95 * len(duracoes)) - 1) if duracoes else 0
            em_fila = sum(
                self._estados.get(estado.value, 0)
                for estado in (EstadoFila.DISPONIVEL, EstadoFila.RESERVADA, EstadoFila.EM_ATENDIMENTO)
            )
            return {
                'schema_version': '1.0.0',
                'fluxo': [estado.value for estado in EstadoFila],
                'quatro_sinais': {
                    'volume': {'transicoes_total': total, 'por_transicao': dict(self._transicoes)},
                    'latencia': {
                        'media_ms': round(mean(duracoes), 2) if duracoes else 0,
                        'p95_ms': duracoes[p95_indice] if duracoes else 0,
                        'amostras': len(duracoes),
                    },
                    'erros': {
                        'total': erros,
                        'taxa_percentual': round((erros / total) * 100, 2) if total else 0,
                        'por_codigo': dict(self._erros),
                    },
                    'saturacao': {
                        'demandas_ativas': em_fila,
                        'por_estado': dict(self._estados),
                    },
                },
                'guardrails': {
                    'sem_pii': True,
                    'demanda_id_anonimizada': True,
                    'cardinalidade_limitada': True,
                },
            }


REGISTRO_FILA = RegistroObservabilidadeFila()


def registrar_transicao_fila(
    *,
    demanda_id: str,
    estado_origem: EstadoFila,
    estado_destino: EstadoFila,
    correlation_id: str,
    inicio: float,
    sucesso: bool = True,
    erro_codigo: str | None = None,
) -> TransicaoFila:
    """API única para instrumentar serviços de fila sem duplicar telemetria."""
    if not correlation_id.strip():
        raise ValueError('correlation_id_obrigatorio')
    evento = TransicaoFila(
        demanda_hash=anonimizar_demanda_id(demanda_id),
        estado_origem=estado_origem,
        estado_destino=estado_destino,
        correlation_id=correlation_id,
        duracao_ms=max(0, round((perf_counter() - inicio) * 1000)),
        sucesso=sucesso,
        erro_codigo=erro_codigo,
    )
    REGISTRO_FILA.registrar(evento)
    return evento



class RepositorioSnapshotsFila:
    """Persistência governada de agregados; não armazena demanda ou correlation_id."""

    def __init__(self, database_url: str, limite: int = 200) -> None:
        if limite < 1:
            raise ValueError('limite_deve_ser_positivo')
        self._limite = limite
        self._engine = create_engine(database_url)
        metadata = MetaData()
        self._tabela = Table(
            'observabilidade_fila_snapshot',
            metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('gerado_em', DateTime(timezone=True), nullable=False),
            Column('payload_json', Text, nullable=False),
        )
        metadata.create_all(self._engine)

    def registrar(self, snapshot: dict) -> None:
        payload = {
            'schema_version': snapshot['schema_version'],
            'fluxo': snapshot['fluxo'],
            'quatro_sinais': snapshot['quatro_sinais'],
            'guardrails': snapshot['guardrails'],
        }
        with self._engine.begin() as conexao:
            conexao.execute(
                self._tabela.insert().values(
                    gerado_em=datetime.now(UTC),
                    payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                )
            )
            ids_excedentes = [
                item[0]
                for item in conexao.execute(
                    select(self._tabela.c.id)
                    .order_by(self._tabela.c.id.desc())
                    .offset(self._limite)
                )
            ]
            if ids_excedentes:
                conexao.execute(self._tabela.delete().where(self._tabela.c.id.in_(ids_excedentes)))

    def listar(self, limite: int = 20) -> list[dict]:
        limite_seguro = min(max(1, limite), self._limite)
        with self._engine.connect() as conexao:
            linhas = conexao.execute(
                select(self._tabela.c.gerado_em, self._tabela.c.payload_json)
                .order_by(self._tabela.c.id.desc())
                .limit(limite_seguro)
            )
            return [
                {
                    'gerado_em': gerado_em.isoformat(),
                    **json.loads(payload_json),
                }
                for gerado_em, payload_json in linhas
            ]


def renderizar_metricas_prometheus(snapshot: dict) -> str:
    """Exporta métricas agregadas com cardinalidade fixa por estado/transição."""
    sinais = snapshot['quatro_sinais']
    linhas = [
        '# HELP reqsys_fila_transicoes_total Total de transicoes da fila.',
        '# TYPE reqsys_fila_transicoes_total counter',
    ]
    for transicao, total in sorted(sinais['volume']['por_transicao'].items()):
        origem, destino = transicao.split('->', maxsplit=1)
        linhas.append(
            f'reqsys_fila_transicoes_total{{origem="{origem}",destino="{destino}"}} {total}'
        )
    linhas.extend(
        [
            '# HELP reqsys_fila_latencia_p95_ms Latencia P95 das transicoes em milissegundos.',
            '# TYPE reqsys_fila_latencia_p95_ms gauge',
            f"reqsys_fila_latencia_p95_ms {sinais['latencia']['p95_ms']}",
            '# HELP reqsys_fila_erros_total Total de erros nas transicoes.',
            '# TYPE reqsys_fila_erros_total counter',
            f"reqsys_fila_erros_total {sinais['erros']['total']}",
            '# HELP reqsys_fila_demandas_ativas Demandas ainda ativas na fila.',
            '# TYPE reqsys_fila_demandas_ativas gauge',
            f"reqsys_fila_demandas_ativas {sinais['saturacao']['demandas_ativas']}",
        ]
    )
    for estado in EstadoFila:
        total = sinais['saturacao']['por_estado'].get(estado.value, 0)
        linhas.append(f'reqsys_fila_estado_total{{estado="{estado.value}"}} {total}')
    return '\n'.join(linhas) + '\n'


def criar_cards_dashboard_fila(snapshot: dict) -> list[dict]:
    sinais = snapshot['quatro_sinais']
    return [
        {
            'id': 'fila-volume',
            'titulo': 'Volume da fila',
            'valor': sinais['volume']['transicoes_total'],
            'unidade': 'transições',
            'drilldown': '/api/runtime/fila/historico',
        },
        {
            'id': 'fila-latencia-p95',
            'titulo': 'Latência P95',
            'valor': sinais['latencia']['p95_ms'],
            'unidade': 'ms',
            'drilldown': '/api/runtime/fila/metricas',
        },
        {
            'id': 'fila-erros',
            'titulo': 'Taxa de erros',
            'valor': sinais['erros']['taxa_percentual'],
            'unidade': '%',
            'drilldown': '/api/runtime/fila/historico',
        },
        {
            'id': 'fila-saturacao',
            'titulo': 'Demandas ativas',
            'valor': sinais['saturacao']['demandas_ativas'],
            'unidade': 'demandas',
            'drilldown': '/api/runtime/fila/historico',
        },
    ]



@dataclass(frozen=True, slots=True)
class PoliticaSLOFila:
    taxa_erros_maxima_percentual: float = 5.0
    latencia_p95_maxima_ms: int = 2000
    demandas_ativas_maximas: int = 50
    amostras_crescimento: int = 3

    @classmethod
    def de_ambiente(cls) -> 'PoliticaSLOFila':
        return cls(
            taxa_erros_maxima_percentual=float(
                os.getenv('FILA_SLO_TAXA_ERROS_MAXIMA_PERCENTUAL', '5')
            ),
            latencia_p95_maxima_ms=int(os.getenv('FILA_SLO_LATENCIA_P95_MAXIMA_MS', '2000')),
            demandas_ativas_maximas=int(os.getenv('FILA_SLO_DEMANDAS_ATIVAS_MAXIMAS', '50')),
            amostras_crescimento=int(os.getenv('FILA_SLO_AMOSTRAS_CRESCIMENTO', '3')),
        )


def avaliar_slos_fila(
    snapshot: dict,
    historico: list[dict],
    politica: PoliticaSLOFila | None = None,
) -> dict:
    politica_ativa = politica or PoliticaSLOFila.de_ambiente()
    sinais = snapshot['quatro_sinais']
    alertas: list[dict] = []

    def adicionar_alerta(codigo: str, severidade: str, valor: float, limite: float) -> None:
        alertas.append(
            {
                'codigo': codigo,
                'severidade': severidade,
                'valor_observado': valor,
                'limite': limite,
                'acao': 'investigar_por_correlation_id_e_transicao',
            }
        )

    taxa_erros = sinais['erros']['taxa_percentual']
    if taxa_erros > politica_ativa.taxa_erros_maxima_percentual:
        adicionar_alerta(
            'FILA_TAXA_ERROS_ACIMA_SLO',
            'critica',
            taxa_erros,
            politica_ativa.taxa_erros_maxima_percentual,
        )

    latencia_p95 = sinais['latencia']['p95_ms']
    if latencia_p95 > politica_ativa.latencia_p95_maxima_ms:
        adicionar_alerta(
            'FILA_LATENCIA_P95_ACIMA_SLO',
            'alta',
            latencia_p95,
            politica_ativa.latencia_p95_maxima_ms,
        )

    demandas_ativas = sinais['saturacao']['demandas_ativas']
    if demandas_ativas > politica_ativa.demandas_ativas_maximas:
        adicionar_alerta(
            'FILA_SATURACAO_ACIMA_SLO',
            'alta',
            demandas_ativas,
            politica_ativa.demandas_ativas_maximas,
        )

    janela = historico[: politica_ativa.amostras_crescimento - 1]
    serie = [
        item['quatro_sinais']['saturacao']['demandas_ativas']
        for item in reversed(janela)
    ] + [demandas_ativas]
    if len(serie) >= politica_ativa.amostras_crescimento and all(
        atual > anterior for anterior, atual in zip(serie, serie[1:], strict=False)
    ):
        alertas.append(
            {
                'codigo': 'FILA_CRESCIMENTO_CONTINUO',
                'severidade': 'alta',
                'valor_observado': serie,
                'limite': politica_ativa.amostras_crescimento,
                'acao': 'verificar_consumidores_e_demandas_presas',
            }
        )

    return {
        'schema_version': '1.0.0',
        'status': 'alerta' if alertas else 'dentro_do_slo',
        'alertas': alertas,
        'politica': {
            'taxa_erros_maxima_percentual': politica_ativa.taxa_erros_maxima_percentual,
            'latencia_p95_maxima_ms': politica_ativa.latencia_p95_maxima_ms,
            'demandas_ativas_maximas': politica_ativa.demandas_ativas_maximas,
            'amostras_crescimento': politica_ativa.amostras_crescimento,
        },
        'guardrails': {
            'somente_avaliacao': True,
            'sem_disparo_externo': True,
            'sem_pii': True,
        },
    }
