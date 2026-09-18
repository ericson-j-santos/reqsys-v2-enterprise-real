"""Adaptador multipass para Tesseract CLI + ImageMagick/Poppler."""
from __future__ import annotations
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from ..dominio.nome import LeituraOCRNome

__all__ = ["DependenciaOCRAusente", "FalhaOCR", "ConfiguracaoOCRNome", "ResultadoOCRMultipass", "TesseractMultipass"]

class DependenciaOCRAusente(RuntimeError):
    pass

class FalhaOCR(RuntimeError):
    pass

@dataclass(frozen=True)
class ConfiguracaoOCRNome:
    idioma: str = "por"
    dpi_pdf: int = 300
    timeout_segundos: float = 60.0
    recorte: tuple[int, int, int, int] | None = None
    psm: tuple[int, int, int] = (7, 7, 7)

@dataclass(frozen=True)
class ResultadoOCRMultipass:
    leituras: tuple[LeituraOCRNome, ...]
    recorte_processado: Path
    variantes: tuple[Path, ...]

def _executar(cmd: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as erro:
        raise FalhaOCR(f"timeout executando {cmd[0]}") from erro
    except OSError as erro:
        raise FalhaOCR(f"falha executando {cmd[0]}: {erro}") from erro
    if proc.returncode != 0:
        detalhe = (proc.stderr or proc.stdout or "").strip()[-1500:]
        raise FalhaOCR(f"{cmd[0]} retornou {proc.returncode}: {detalhe}")
    return proc

def _numero_titulo(titulo: str, chave: str) -> float | None:
    achado = re.search(rf"(?:^|[;\s]){re.escape(chave)}\s+(-?\d+(?:\.\d+)?)", titulo or "")
    return float(achado.group(1)) if achado else None

def _ler_hocr(hocr: str) -> tuple[str, float, tuple[float, ...]]:
    try:
        raiz = ET.fromstring(hocr)
    except ET.ParseError as erro:
        raise FalhaOCR(f"hOCR inválido: {erro}") from erro
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    palavras: list[str] = []
    conf_palavras: list[float] = []
    conf_chars_saida: list[float] = []
    for word in raiz.findall(".//x:span[@class='ocrx_word']", ns):
        wconf = _numero_titulo(word.attrib.get("title", ""), "x_wconf")
        if wconf is not None and wconf >= 0:
            conf_palavras.append(max(0.0, min(1.0, wconf / 100.0)))
        chars: list[str] = []
        confs: list[float] = []
        for span in word.findall("./x:span[@class='ocrx_cinfo']", ns):
            titulo = span.attrib.get("title", "")
            if "x_bboxes" not in titulo or "x_conf" not in titulo:
                continue
            char = span.text or ""
            if not char:
                continue
            conf = _numero_titulo(titulo, "x_conf")
            chars.append(char)
            confs.append(max(0.0, min(1.0, (conf or 0.0) / 100.0)))
        palavra = "".join(chars).strip()
        if palavra:
            if palavras:
                conf_chars_saida.append(1.0)
            palavras.append(palavra)
            conf_chars_saida.extend(confs[:len(palavra)])
    texto = " ".join(palavras).strip()
    confianca = sum(conf_palavras) / len(conf_palavras) if conf_palavras else 0.0
    if len(conf_chars_saida) != len(texto):
        conf_chars_saida = []
    return texto, max(0.0, min(1.0, confianca)), tuple(conf_chars_saida)

class TesseractMultipass:
    def __init__(self, config: ConfiguracaoOCRNome | None = None) -> None:
        self.config = config or ConfiguracaoOCRNome()
        self.tesseract = shutil.which("tesseract")
        self.pdftoppm = shutil.which("pdftoppm")
        self.magick = shutil.which("magick") or shutil.which("convert")
        if not self.tesseract:
            raise DependenciaOCRAusente("tesseract não encontrado no PATH")
        self._validar_idioma()

    def _validar_idioma(self) -> None:
        proc = _executar([self.tesseract, "--list-langs"], self.config.timeout_segundos)
        idiomas = {x.strip() for x in proc.stdout.splitlines()[1:] if x.strip()}
        if self.config.idioma not in idiomas:
            raise DependenciaOCRAusente(f"idioma Tesseract '{self.config.idioma}' não instalado; disponíveis: {', '.join(sorted(idiomas)[:20])}")

    def _rasterizar(self, entrada: Path, trabalho: Path) -> Path:
        if entrada.suffix.lower() == ".pdf":
            if not self.pdftoppm:
                raise DependenciaOCRAusente("pdftoppm não encontrado; necessário para PDF")
            base = trabalho / "pagina"
            _executar([self.pdftoppm, "-f", "1", "-singlefile", "-png", "-r", str(self.config.dpi_pdf), str(entrada), str(base)], self.config.timeout_segundos)
            imagem = base.with_suffix(".png")
            if not imagem.is_file():
                raise FalhaOCR("pdftoppm não gerou a imagem esperada")
            return imagem
        destino = trabalho / "entrada.png"
        if self.magick:
            _executar([self.magick, str(entrada), str(destino)], self.config.timeout_segundos)
        else:
            shutil.copy2(entrada, destino)
        return destino

    def _recortar(self, imagem: Path, trabalho: Path) -> Path:
        if not self.config.recorte:
            return imagem
        if not self.magick:
            raise DependenciaOCRAusente("ImageMagick é necessário quando recorte é usado")
        x, y, largura, altura = self.config.recorte
        if min(x, y, largura, altura) < 0 or largura <= 0 or altura <= 0:
            raise ValueError("recorte inválido")
        destino = trabalho / "recorte.png"
        _executar([self.magick, str(imagem), "-crop", f"{largura}x{altura}+{x}+{y}", "+repage", str(destino)], self.config.timeout_segundos)
        return destino

    def _variantes(self, imagem: Path, trabalho: Path) -> list[Path]:
        original = trabalho / "passo_a.png"
        if self.magick:
            _executar([self.magick, str(imagem), str(original)], self.config.timeout_segundos)
            melhorada = trabalho / "passo_b.png"
            binaria = trabalho / "passo_c.png"
            _executar([self.magick, str(imagem), "-colorspace", "Gray", "-resize", "250%", "-deskew", "40%", "-contrast-stretch", "1%x1%", "-sharpen", "0x1", str(melhorada)], self.config.timeout_segundos)
            _executar([self.magick, str(imagem), "-colorspace", "Gray", "-resize", "300%", "-deskew", "40%", "-auto-level", "-threshold", "58%", str(binaria)], self.config.timeout_segundos)
            return [original, melhorada, binaria]
        shutil.copy2(imagem, original)
        return [original, original, original]

    def _ocr(self, imagem: Path, psm: int, origem: str) -> LeituraOCRNome:
        proc = _executar([self.tesseract, str(imagem), "stdout", "-l", self.config.idioma, "--psm", str(psm), "-c", "preserve_interword_spaces=1", "-c", "load_system_dawg=0", "-c", "load_freq_dawg=0", "-c", "hocr_char_boxes=1", "-c", "lstm_choice_mode=2", "hocr"], self.config.timeout_segundos)
        texto, confianca, conf_chars = _ler_hocr(proc.stdout)
        return LeituraOCRNome(texto=texto, confianca=confianca, origem=origem, confiancas_caracteres=conf_chars)

    def executar(self, entrada: str | Path, *, diretorio_trabalho: str | Path | None = None) -> ResultadoOCRMultipass:
        entrada = Path(entrada)
        if not entrada.is_file():
            raise FileNotFoundError(entrada)
        if diretorio_trabalho is None:
            diretorio_trabalho = tempfile.mkdtemp(prefix="ocr_nome_")
        trabalho = Path(diretorio_trabalho)
        trabalho.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(trabalho, 0o700)
        except OSError:
            pass
        imagem = self._rasterizar(entrada, trabalho)
        recorte = self._recortar(imagem, trabalho)
        variantes = self._variantes(recorte, trabalho)
        leituras = tuple(self._ocr(variante, psm, origem=f"passo_{chr(65+i)}:psm{psm}") for i, (variante, psm) in enumerate(zip(variantes, self.config.psm)))
        return ResultadoOCRMultipass(leituras=leituras, recorte_processado=recorte, variantes=tuple(variantes))
