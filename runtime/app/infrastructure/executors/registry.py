"""Registro de executores: de ``ExecutorKind`` para o adaptador concreto.

Um executor sem adaptador configurado **não é ignorado em silêncio**: o worker
bloqueia a solicitação nomeando exatamente o que falta configurar. Fila parada
sem explicação foi um dos gargalos que a Central existe para eliminar.
"""

from __future__ import annotations

import json
from typing import Any

from app.domain.central.execution import ExecutorAdapter
from app.domain.central.models import ExecutorKind
from app.infrastructure.executors.http_executor import HttpExecutorAdapter, HttpExecutorEndpoint


class ExecutorRegistry:
    def __init__(self, adaptadores: dict[ExecutorKind, ExecutorAdapter] | None = None) -> None:
        self._adaptadores = dict(adaptadores or {})

    def registrar(self, kind: ExecutorKind, adaptador: ExecutorAdapter) -> None:
        self._adaptadores[kind] = adaptador

    def para(self, kind: ExecutorKind) -> ExecutorAdapter | None:
        return self._adaptadores.get(kind)

    def configurados(self) -> tuple[ExecutorKind, ...]:
        return tuple(sorted(self._adaptadores, key=lambda item: item.value))


def registry_de_configuracao(bruto: str, service_token: str = "") -> ExecutorRegistry:
    """Constrói o registro a partir de ``CENTRAL_EXECUTOR_ENDPOINTS`` (JSON).

    Formato aceito::

        {"ci_repair": "https://executor/ci",
         "graph": {"url": "https://executor/graph",
                   "negative_probe": {"sha": "invalido"}}}

    ``human_gate`` nunca pode receber adaptador: é a marca de que a próxima ação
    é de uma pessoa, e automatizá-lo anularia o próprio gate.
    """
    if not bruto or not bruto.strip():
        return ExecutorRegistry()

    try:
        dados: Any = json.loads(bruto)
    except json.JSONDecodeError as exc:
        raise ValueError(f"CENTRAL_EXECUTOR_ENDPOINTS não é JSON válido: {exc}") from exc

    if not isinstance(dados, dict):
        raise ValueError("CENTRAL_EXECUTOR_ENDPOINTS deve ser um objeto JSON")

    adaptadores: dict[ExecutorKind, ExecutorAdapter] = {}
    for nome, valor in dados.items():
        try:
            kind = ExecutorKind(nome)
        except ValueError as exc:
            validos = ", ".join(sorted(item.value for item in ExecutorKind))
            raise ValueError(f"executor desconhecido '{nome}'; válidos: {validos}") from exc

        if kind is ExecutorKind.HUMAN_GATE:
            raise ValueError("human_gate não aceita executor automático")

        adaptadores[kind] = HttpExecutorAdapter(
            _endpoint(kind, valor), service_token=service_token
        )

    return ExecutorRegistry(adaptadores)


def _endpoint(kind: ExecutorKind, valor: Any) -> HttpExecutorEndpoint:
    if isinstance(valor, str):
        return HttpExecutorEndpoint(url=valor)
    if isinstance(valor, dict) and isinstance(valor.get("url"), str):
        probe = valor.get("negative_probe")
        if probe is not None and not isinstance(probe, dict):
            raise ValueError(f"negative_probe de '{kind.value}' deve ser um objeto JSON")
        return HttpExecutorEndpoint(url=valor["url"], negative_probe=probe)
    raise ValueError(f"configuração inválida para '{kind.value}': informe a URL do executor")
