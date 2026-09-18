"""Modelos de domínio da rotina de e-mail de Prospecção Movimento (ADR-001).

Dataclasses puras — sem SQLAlchemy, pyodbc, Jinja2 ou qualquer dependência de
infraestrutura. `repository.py` (extração) e `transform.py` produzem estes
tipos; `email_service.py` (renderização) apenas os consome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class ItemFechamento:
    """Um indicador consolidado do fechamento diário."""

    indicador: str
    valor: str
    observacao: str = ''


@dataclass(frozen=True)
class ItemPendenciaCadastro:
    """Registro concluído operacionalmente mas com pendência cadastral em aberto."""

    protocolo: str
    cliente: str
    cpf: str
    pendencia: str
    dias_em_aberto: int
    responsavel: str = ''


@dataclass(frozen=True)
class ItemPendenciaHistorica:
    """Linha do consolidado histórico de pendências (série por período)."""

    periodo_referencia: str
    pendencia: str
    quantidade: int
    percentual: float


@dataclass(frozen=True)
class ItemPendenciaObservacao:
    """Inconsistência agrupada encontrada durante o processamento."""

    protocolo: str
    tipo_inconsistencia: str
    descricao: str
    etapa: str = ''


@dataclass(frozen=True)
class ContextoEmailMovimento:
    """Contexto agregado pronto para renderização (saída de `transform.py`)."""

    data_referencia: date
    correlation_id: str
    fechamento: list[ItemFechamento] = field(default_factory=list)
    pendencias_cadastro: list[ItemPendenciaCadastro] = field(default_factory=list)
    pendencias_historicas: list[ItemPendenciaHistorica] = field(default_factory=list)
    pendencias_observacao: list[ItemPendenciaObservacao] = field(default_factory=list)

    @property
    def total_pendencias(self) -> int:
        return (
            len(self.pendencias_cadastro)
            + len(self.pendencias_historicas)
            + len(self.pendencias_observacao)
        )
