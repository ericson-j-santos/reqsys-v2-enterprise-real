"""OCR de documento completo para apoiar a construção de demandas.

Este worker é separado do OCR especializado em nomes. Ele preserva a página de
origem, não publica texto/PII no barramento e falha fechado quando as
dependências nativas não estão disponíveis.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.services.documento_demanda import TIPOS_OCR_DOCUMENTO
from app.services.runtime_core import RuntimeEventBus, RuntimeEventEnvelope

EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO = 'OCR_DOCUMENTO_DEMANDA_SOLICITADO'


class DependenciaOcrDocumentoAusente(RuntimeError):
    pass


class FalhaOcrDocumento(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrPaginaDocumento:
    pagina: int
    texto: str
    confianca: float


@dataclass(frozen=True)
class OcrDocumentoResultado:
    paginas: tuple[OcrPaginaDocumento, ...]
    engine: str = 'tesseract-tsv'

    @property
    def texto(self) -> str:
        return '\n\n'.join(item.texto for item in self.paginas if item.texto.strip())


class MotorOcrDocumento(Protocol):
    def processar(self, entrada: Path, *, content_type: str) -> OcrDocumentoResultado: ...


@dataclass
class RepositorioOcrDocumentoMemoria:
    _resultados: dict[str, OcrDocumentoResultado] = field(default_factory=dict)

    def salvar(self, job_id: str, resultado: OcrDocumentoResultado) -> None:
        self._resultados[job_id] = resultado

    def obter(self, job_id: str) -> OcrDocumentoResultado | None:
        return self._resultados.get(job_id)


def _executar(cmd: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise FalhaOcrDocumento(f'timeout executando {Path(cmd[0]).name}') from exc
    except OSError as exc:
        raise FalhaOcrDocumento(f'falha executando {Path(cmd[0]).name}') from exc
    if proc.returncode != 0:
        raise FalhaOcrDocumento(f'{Path(cmd[0]).name} retornou código {proc.returncode}')
    return proc


def _numero_pagina(path: Path) -> int:
    achado = re.search(r'-(\d+)$', path.stem)
    return int(achado.group(1)) if achado else 1


def _ler_tsv(tsv: str) -> tuple[str, float]:
    linhas: dict[tuple[str, str, str, str], list[str]] = {}
    confiancas: list[float] = []
    reader = csv.DictReader(io.StringIO(tsv), delimiter='\t')
    for item in reader:
        texto = (item.get('text') or '').strip()
        if not texto:
            continue
        chave = (
            item.get('block_num') or '0',
            item.get('par_num') or '0',
            item.get('line_num') or '0',
            item.get('page_num') or '1',
        )
        linhas.setdefault(chave, []).append(texto)
        try:
            confianca = float(item.get('conf') or '-1')
        except ValueError:
            confianca = -1
        if confianca >= 0:
            confiancas.append(max(0.0, min(1.0, confianca / 100.0)))
    texto_saida = '\n'.join(' '.join(palavras) for palavras in linhas.values()).strip()
    confianca_saida = sum(confiancas) / len(confiancas) if confiancas else 0.0
    return texto_saida, round(confianca_saida, 6)


class TesseractDocumento:
    """Extrai texto de todas as páginas, com limite explícito e referência de página."""

    def __init__(
        self,
        *,
        idioma: str = 'por',
        dpi_pdf: int = 200,
        timeout_segundos: float = 60.0,
        max_paginas: int = 25,
    ) -> None:
        self.idioma = idioma
        self.dpi_pdf = dpi_pdf
        self.timeout_segundos = timeout_segundos
        self.max_paginas = max_paginas
        self.tesseract = shutil.which('tesseract')
        self.pdftoppm = shutil.which('pdftoppm')
        self.pdfinfo = shutil.which('pdfinfo')
        if not self.tesseract:
            raise DependenciaOcrDocumentoAusente('tesseract não encontrado no PATH')
        self._validar_idioma()

    def _validar_idioma(self) -> None:
        proc = _executar([self.tesseract, '--list-langs'], self.timeout_segundos)
        idiomas = {linha.strip() for linha in proc.stdout.splitlines()[1:] if linha.strip()}
        if self.idioma not in idiomas:
            raise DependenciaOcrDocumentoAusente(f'idioma Tesseract {self.idioma!r} não instalado')

    def _validar_paginas_pdf(self, entrada: Path) -> None:
        if not self.pdfinfo:
            raise DependenciaOcrDocumentoAusente('pdfinfo não encontrado; necessário para limitar páginas')
        proc = _executar([self.pdfinfo, str(entrada)], self.timeout_segundos)
        achado = re.search(r'^Pages:\s+(\d+)\s*$', proc.stdout, flags=re.MULTILINE | re.IGNORECASE)
        if not achado:
            raise FalhaOcrDocumento('não foi possível determinar a quantidade de páginas do PDF')
        paginas = int(achado.group(1))
        if paginas > self.max_paginas:
            raise FalhaOcrDocumento(f'PDF excede o limite de {self.max_paginas} páginas para OCR')

    def _rasterizar(self, entrada: Path, content_type: str, trabalho: Path) -> list[Path]:
        if content_type == 'application/pdf':
            if not self.pdftoppm:
                raise DependenciaOcrDocumentoAusente('pdftoppm não encontrado; necessário para PDF')
            self._validar_paginas_pdf(entrada)
            base = trabalho / 'pagina'
            _executar(
                [self.pdftoppm, '-png', '-r', str(self.dpi_pdf), str(entrada), str(base)],
                self.timeout_segundos,
            )
            paginas = sorted(trabalho.glob('pagina-*.png'), key=_numero_pagina)
            if not paginas:
                raise FalhaOcrDocumento('pdftoppm não gerou páginas para OCR')
            return paginas
        return [entrada]

    def _ocr_pagina(self, imagem: Path, pagina: int) -> OcrPaginaDocumento:
        proc = _executar(
            [self.tesseract, str(imagem), 'stdout', '-l', self.idioma, '--psm', '6', 'tsv'],
            self.timeout_segundos,
        )
        texto, confianca = _ler_tsv(proc.stdout)
        return OcrPaginaDocumento(pagina=pagina, texto=texto, confianca=confianca)

    def processar(self, entrada: Path, *, content_type: str) -> OcrDocumentoResultado:
        if content_type not in TIPOS_OCR_DOCUMENTO:
            raise ValueError('tipo de arquivo não suportado pelo OCR de documento')
        if not entrada.is_file():
            raise FileNotFoundError(entrada)
        with tempfile.TemporaryDirectory(prefix='reqsys_ocr_documento_') as temp:
            trabalho = Path(temp)
            paginas = self._rasterizar(entrada, content_type, trabalho)
            resultados = tuple(
                self._ocr_pagina(path, indice if content_type != 'application/pdf' else _numero_pagina(path))
                for indice, path in enumerate(paginas, start=1)
            )
        resultado = OcrDocumentoResultado(paginas=resultados)
        if not resultado.texto.strip():
            raise FalhaOcrDocumento('OCR não extraiu texto utilizável do documento')
        return resultado


class DocumentoDemandaOcrWorker:
    def __init__(
        self,
        motor: MotorOcrDocumento,
        repositorio: RepositorioOcrDocumentoMemoria,
        *,
        input_root: str | Path,
    ) -> None:
        self.motor = motor
        self.repositorio = repositorio
        self.input_root = Path(input_root).resolve()

    def __call__(self, envelope: RuntimeEventEnvelope) -> None:
        if envelope.event_type != EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO:
            raise ValueError(f'evento não suportado pelo worker OCR de documento: {envelope.event_type}')
        document_ref = str(envelope.payload.get('document_ref', '')).strip()
        content_type = str(envelope.payload.get('content_type', '')).strip()
        if not document_ref:
            raise ValueError('document_ref é obrigatório')
        if Path(document_ref).is_absolute():
            raise ValueError('document_ref deve ser relativo ao diretório de entrada')
        entrada = (self.input_root / document_ref).resolve()
        if not entrada.is_relative_to(self.input_root):
            raise ValueError('document_ref escapou do diretório de entrada')
        if not entrada.is_file():
            raise FileNotFoundError(entrada)
        resultado = self.motor.processar(entrada, content_type=content_type)
        self.repositorio.salvar(envelope.aggregate_id, resultado)


def registrar_documento_demanda_ocr_worker(bus: RuntimeEventBus, worker: DocumentoDemandaOcrWorker) -> None:
    bus.subscribe(EVENTO_OCR_DOCUMENTO_DEMANDA_SOLICITADO, worker)


def ocr_documento_readiness() -> dict[str, object]:
    tesseract = shutil.which('tesseract')
    pdftoppm = shutil.which('pdftoppm')
    pdfinfo = shutil.which('pdfinfo')
    return {
        'tesseract': bool(tesseract),
        'pdftoppm': bool(pdftoppm),
        'pdfinfo': bool(pdfinfo),
        'ready_images': bool(tesseract),
        'ready_pdf': bool(tesseract and pdftoppm and pdfinfo),
    }
