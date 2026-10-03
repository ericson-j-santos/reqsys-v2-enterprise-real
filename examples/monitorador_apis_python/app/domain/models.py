from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ResultadoMonitoramento:
    nome: str
    url: str
    status_code: int | None
    sucesso: bool
    tempo_resposta_ms: float
    erro: str | None
    consultado_em: datetime

    @property
    def status_operacional(self) -> str:
        if self.sucesso and self.tempo_resposta_ms <= 1000:
            return "VERDE"

        if self.sucesso and self.tempo_resposta_ms <= 2500:
            return "AMARELO"

        return "VERMELHO"
