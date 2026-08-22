"""Worker OCR governado integrado ao Runtime Core do ReqSys.

Princípios:
- entrada referenciada por caminho relativo sob ``OCR_INPUT_ROOT``;
- nenhuma PII é publicada no envelope de auditoria do Runtime Core;
- ``AUTO/VALIDACAO_ADICIONAL/REVISAO/ABSTENCAO`` é estado de domínio OCR,
  não substitui os estados técnicos do Runtime Core;
- dependências OCR e erros de leitura falham fechado e seguem retry/DLQ do bus;
- motor é injetável para testes e futuras trocas de engine.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.services.runtime_core import RuntimeEventBus, RuntimeEventEnvelope
from ocr_evidencia import __version__ as OCR_EVIDENCIA_VERSION
from ocr_evidencia.adaptadores.ocr_tesseract import (
    ConfiguracaoOCRNome,
    TesseractMultipass,
)
from ocr_evidencia.dominio.nome import ResultadoConsensoNome, consensuar_nome

EVENTO_OCR_SOLICITADO = 'OCR_DOCUMENTO_SOLICITADO'

@dataclass(frozen=True)
class OcrResultado:
    job_id: str
    correlation_id: str
    tipo_documento: str
    campo: str
    estado_ocr: str
    confianca: float
    valor: str
    motivos: tuple[str, ...] = ()
    engine_version: str = OCR_EVIDENCIA_VERSION

    def auditoria_sem_pii(self) -> dict[str, object]:
        return {
            'job_id': self.job_id,
            'correlation_id': self.correlation_id,
            'tipo_documento': self.tipo_documento,
            'campo': self.campo,
            'estado_ocr': self.estado_ocr,
            'confianca': round(self.confianca, 6),
            'motivos': list(self.motivos),
            'engine_version': self.engine_version,
        }

class MotorOcrNome(Protocol):
    def processar(self, entrada: Path, *, recorte: tuple[int, int, int, int] | None = None) -> ResultadoConsensoNome: ...

class RepositorioResultadosOcr(Protocol):
    def salvar(self, resultado: OcrResultado) -> None: ...

@dataclass
class RepositorioResultadosOcrMemoria:
    """Adapter apenas para DEV/teste. Não deve ser usado como store produtivo."""
    _resultados: dict[str, OcrResultado] = field(default_factory=dict)

    def salvar(self, resultado: OcrResultado) -> None:
        self._resultados[resultado.job_id] = resultado

    def obter(self, job_id: str) -> OcrResultado | None:
        return self._resultados.get(job_id)

class MotorOcrEvidencia:
    """Adapter do ReqSys para a fatia executável ``ocr_evidencia`` v1.2.0."""
    def __init__(self, *, idioma: str = 'por', dpi_pdf: int = 300, timeout_segundos: float = 60.0) -> None:
        self.idioma = idioma
        self.dpi_pdf = dpi_pdf
        self.timeout_segundos = timeout_segundos

    def processar(self, entrada: Path, *, recorte=None) -> ResultadoConsensoNome:
        config = ConfiguracaoOCRNome(idioma=self.idioma, dpi_pdf=self.dpi_pdf, timeout_segundos=self.timeout_segundos, recorte=recorte)
        multipass = TesseractMultipass(config).executar(entrada)
        return consensuar_nome(multipass.leituras)

class OcrWorker:
    def __init__(self, motor: MotorOcrNome, repositorio: RepositorioResultadosOcr, *, input_root: str | Path | None = None) -> None:
        self.motor = motor
        self.repositorio = repositorio
        root = input_root or os.getenv('OCR_INPUT_ROOT')
        if not root:
            raise ValueError('OCR_INPUT_ROOT é obrigatório quando input_root não for informado')
        self.input_root = Path(root).resolve()

    def __call__(self, envelope: RuntimeEventEnvelope) -> None:
        if envelope.event_type != EVENTO_OCR_SOLICITADO:
            raise ValueError(f'evento não suportado pelo worker OCR: {envelope.event_type}')
        payload = envelope.payload
        campo = str(payload.get('campo', 'nome')).strip().lower()
        if campo != 'nome':
            raise ValueError('incremento OCR v1 suporta somente campo nome')
        document_ref = str(payload.get('document_ref', '')).strip()
        if not document_ref:
            raise ValueError('document_ref é obrigatório')
        if Path(document_ref).is_absolute():
            raise ValueError('document_ref deve ser relativo ao OCR_INPUT_ROOT')
        entrada = (self.input_root / document_ref).resolve()
        if not entrada.is_relative_to(self.input_root):
            raise ValueError('document_ref escapou do OCR_INPUT_ROOT')
        if not entrada.is_file():
            raise FileNotFoundError(entrada)
        recorte = _ler_recorte(payload.get('recorte'))
        consenso = self.motor.processar(entrada, recorte=recorte)
        self.repositorio.salvar(OcrResultado(
            job_id=envelope.aggregate_id,
            correlation_id=envelope.correlation_id,
            tipo_documento=str(payload.get('tipo_documento', 'DESCONHECIDO')),
            campo=campo,
            estado_ocr=consenso.estado.value,
            confianca=consenso.confianca,
            valor=consenso.valor,
            motivos=consenso.motivos,
        ))

def _ler_recorte(valor: object) -> tuple[int, int, int, int] | None:
    if valor in (None, ''):
        return None
    if not isinstance(valor, (list, tuple)) or len(valor) != 4:
        raise ValueError('recorte deve conter [x, y, largura, altura]')
    try:
        x, y, largura, altura = (int(v) for v in valor)
    except (TypeError, ValueError) as exc:
        raise ValueError('recorte deve conter quatro inteiros') from exc
    if x < 0 or y < 0 or largura <= 0 or altura <= 0:
        raise ValueError('recorte inválido')
    return x, y, largura, altura

def registrar_ocr_worker(bus: RuntimeEventBus, worker: OcrWorker) -> None:
    bus.subscribe(EVENTO_OCR_SOLICITADO, worker)
