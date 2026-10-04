from pydantic import BaseModel, Field


class ItemMonitorado(BaseModel):
    tipo: str
    referencia: str
    titulo: str
    estado: str = Field(pattern='^(verde|amarelo|vermelho|bloqueado|desconhecido)$')
    severidade: str = Field(pattern='^(baixa|media|alta|critica)$')
    origem: str
    pronto_para_merge: bool = False
    bloqueante: bool = False
    proximo_passo: str | None = None
    criterio_de_fechamento: str | None = None
    detalhes: dict = Field(default_factory=dict)


class ResumoMonitoramento(BaseModel):
    estado_geral: str
    bloqueios: int
    pendencias: int
    total_itens: int
    frentes_criticas: int = 0
    itens_prontos_para_merge: int = 0


class TempoOperacional(BaseModel):
    previsao_proxima_acao: str
    eta_proxima_verificacao_minutos: int
    tempo_medio_proxima_acao_minutos: int
    tempo_medio_resolucao_horas: float
    tempo_medio_review_minutos: int
    sla_operacional_minutos: int


class MonitoramentoOperacional(BaseModel):
    schema_version: str = '1.2.0'
    correlation_id: str
    coletado_em: str
    ambiente: str
    modo_coleta: str = Field(default='preview', pattern='^(live|hibrido|preview)$')
    coleta_detalhes: dict = Field(default_factory=dict)
    resumo: ResumoMonitoramento
    tempo_operacional: TempoOperacional
    itens: list[ItemMonitorado]
