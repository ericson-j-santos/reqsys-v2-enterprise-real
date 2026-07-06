from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class ProviderTelemetry:
    """Telemetry in-process, sem persistir prompt, resposta, PII ou segredo."""

    total_requisicoes: int = 0
    sucessos: int = 0
    falhas: int = 0
    fallback_acionado: int = 0
    ultima_chamada_em: str | None = None
    ultimo_sucesso_em: str | None = None
    ultima_falha_em: str | None = None
    ultimo_tipo_erro: str | None = None

    def snapshot(self) -> dict[str, Any]:
        taxa_sucesso = 0.0
        if self.total_requisicoes:
            taxa_sucesso = round((self.sucessos / self.total_requisicoes) * 100, 2)
        return {
            'total_requisicoes': self.total_requisicoes,
            'sucessos': self.sucessos,
            'falhas': self.falhas,
            'fallback_acionado': self.fallback_acionado,
            'taxa_sucesso_pct': taxa_sucesso,
            'ultima_chamada_em': self.ultima_chamada_em,
            'ultimo_sucesso_em': self.ultimo_sucesso_em,
            'ultima_falha_em': self.ultima_falha_em,
            'ultimo_tipo_erro': self.ultimo_tipo_erro,
        }


_lock = threading.Lock()
_telemetry: dict[str, ProviderTelemetry] = defaultdict(ProviderTelemetry)


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def registrar_evento_llm(provider: str, status: str, tipo_erro: str | None = None) -> None:
    """
    Registra evento operacional de LLM sem capturar payload sensível.

    Status suportados:
    - sucesso
    - falha
    - fallback_acionado
    """
    nome_provider = (provider or 'desconhecido').strip().lower()
    status_normalizado = (status or '').strip().lower()
    agora = _agora_iso()

    with _lock:
        item = _telemetry[nome_provider]
        if status_normalizado in {'sucesso', 'falha'}:
            item.total_requisicoes += 1
            item.ultima_chamada_em = agora
        if status_normalizado == 'sucesso':
            item.sucessos += 1
            item.ultimo_sucesso_em = agora
        elif status_normalizado == 'falha':
            item.falhas += 1
            item.ultima_falha_em = agora
            item.ultimo_tipo_erro = tipo_erro or 'erro_indisponivel'
        elif status_normalizado == 'fallback_acionado':
            item.fallback_acionado += 1


def obter_snapshot_telemetry_llm() -> dict[str, Any]:
    """Retorna snapshot serializável para status, health checks e dashboards."""
    with _lock:
        return {provider: telemetry.snapshot() for provider, telemetry in sorted(_telemetry.items())}


def resetar_telemetry_llm() -> None:
    """Uso exclusivo em testes automatizados."""
    with _lock:
        _telemetry.clear()
