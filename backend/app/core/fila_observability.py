"""Telemetria Pareto para fluxos de fila do ReqSys.

Concentra volume, latência, erros e saturação sem persistir PII.
"""

from __future__ import annotations

import hashlib
import threading
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from statistics import mean
from time import perf_counter
from typing import Final

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
