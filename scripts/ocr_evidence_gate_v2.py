#!/usr/bin/env python3
"""OCR Evidence Gate v2.

Gera corpus sintético governado em tempo de execução e valida dez cenários
documentais contra o mesmo motor Tesseract/Poppler usado pelo ReqSys.

O artefato de saída nunca contém texto OCR bruto nem identificadores reais.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
MANIFEST_PATH = ROOT / "benchmark" / "ocr" / "evidence-v2.json"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ocr.documento_worker import FalhaOcrDocumento, TesseractDocumento
from app.services.documento_demanda import (
    CandidatoDemanda,
    calcular_sha256,
    classificar_candidatos_por_paginas,
)

SCHEMA_VERSION = "2.0.0"


@dataclass(frozen=True)
class CaseEvidence:
    case_id: str
    scenario: str
    file_sha256: str
    content_type: str
    pages: int
    confidence_min: float
    confidence_avg: float
    candidates: int
    candidate_types: tuple[str, ...]
    all_candidates_require_human_review: bool
    idempotent: bool
    outcome_fingerprint: str
    status: str
    failures: tuple[str, ...]


def _run(cmd: list[str], timeout: float = 30.0) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        detalhe = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"{Path(cmd[0]).name} falhou ({proc.returncode}): {detalhe[:500]}")


def _imagemagick() -> str:
    executable = shutil.which("magick") or shutil.which("convert")
    if not executable:
        raise RuntimeError("ImageMagick não encontrado")
    return executable


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Z0-9]+", " ", sem_acento.upper()).strip()


def _sha256(path: Path) -> str:
    return calcular_sha256(path.read_bytes())


def _render_png(
    destino: Path,
    linhas: list[str],
    *,
    width: int = 1600,
    height: int = 1000,
    pointsize: int = 54,
    rotate: float = 0.0,
    blur: float = 0.0,
) -> None:
    texto = "\n".join(linhas)
    cmd = [
        _imagemagick(),
        "-size", f"{width}x{height}",
        "xc:white",
        "-gravity", "northwest",
        "-font", "DejaVu-Sans",
        "-pointsize", str(pointsize),
        "-fill", "black",
        "-annotate", "+90+120", texto,
    ]
    if blur > 0:
        cmd.extend(["-blur", f"0x{blur}"])
    if rotate:
        cmd.extend(["-background", "white", "-rotate", str(rotate)])
    cmd.append(str(destino))
    _run(cmd)


def _pdf_texto(destino: Path, paginas: list[list[str]]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(destino), pagesize=A4)
    _, altura = A4
    for linhas in paginas:
        y = altura - 90
        c.setFont("Helvetica", 16)
        for linha in linhas:
            c.drawString(70, y, linha)
            y -= 34
        c.showPage()
    c.save()


def _pdf_imagens(destino: Path, imagens: list[Path]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    largura, altura = A4
    c = canvas.Canvas(str(destino), pagesize=A4)
    for imagem in imagens:
        c.drawImage(
            ImageReader(str(imagem)),
            28,
            28,
            width=largura - 56,
            height=altura - 56,
            preserveAspectRatio=True,
            anchor="c",
        )
        c.showPage()
    c.save()


def _gerar_caso(caso: dict, workdir: Path) -> tuple[Path, str]:
    kind = caso["kind"]
    case_dir = workdir / caso["case_id"]
    case_dir.mkdir(parents=True, exist_ok=True)

    if kind == "searchable_pdf":
        path = case_dir / "searchable.pdf"
        _pdf_texto(path, [["REQUISITO DE TESTE", "O SISTEMA DEVE CADASTRAR A DEMANDA."]])
        return path, "application/pdf"

    if kind == "scanned_pdf":
        image = case_dir / "scan.png"
        _render_png(image, ["DOCUMENTO DIGITALIZADO", "A ROTINA DEVERA REGISTRAR O RESULTADO."])
        path = case_dir / "scanned.pdf"
        _pdf_imagens(path, [image])
        return path, "application/pdf"

    if kind == "multi_document_pdf":
        p1 = case_dir / "contrato.png"
        p2 = case_dir / "comprovante.png"
        _render_png(p1, ["CONTRATO DE TESTE", "SOMENTE DADOS SINTETICOS."])
        _render_png(p2, ["COMPROVANTE DE TESTE", "REFERENCIA SINTETICA 2026."])
        path = case_dir / "multi.pdf"
        _pdf_imagens(path, [p1, p2])
        return path, "application/pdf"

    if kind == "rotated_image":
        path = case_dir / "rotated.png"
        _render_png(path, ["DOCUMENTO ROTACIONADO", "CONTEUDO SINTETICO."], rotate=2.0)
        return path, "image/png"

    if kind == "low_resolution_image":
        path = case_dir / "low.png"
        _render_png(
            path,
            ["BAIXA RESOLUCAO", "DOCUMENTO SINTETICO."],
            width=620,
            height=380,
            pointsize=34,
            blur=0.2,
        )
        return path, "image/png"

    if kind == "mobile_photo_image":
        path = case_dir / "mobile.png"
        _render_png(
            path,
            ["FOTO DE CELULAR", "DOCUMENTO SINTETICO."],
            rotate=1.3,
            blur=0.35,
        )
        return path, "image/png"

    if kind == "identity_proof_bundle":
        specs = [
            ["CPF SINTETICO", "000.000.000-00", "NAO UTILIZAR COMO IDENTIFICADOR REAL"],
            ["RG CIN SINTETICO", "00.000.000-0", "NAO UTILIZAR COMO IDENTIFICADOR REAL"],
            ["CNH SINTETICA", "00000000000", "NAO UTILIZAR COMO IDENTIFICADOR REAL"],
            ["COMPROVANTE SINTETICO", "ENDERECO DE TESTE", "SEM DADOS PESSOAIS REAIS"],
        ]
        images: list[Path] = []
        for index, linhas in enumerate(specs, 1):
            image = case_dir / f"doc-{index}.png"
            _render_png(image, linhas, pointsize=46)
            images.append(image)
        path = case_dir / "identity-proof.pdf"
        _pdf_imagens(path, images)
        return path, "application/pdf"

    if kind == "blank_page":
        path = case_dir / "blank.pdf"
        _pdf_texto(path, [[]])
        return path, "application/pdf"

    if kind == "unknown_document":
        path = case_dir / "unknown.png"
        _render_png(path, ["DOCUMENTO DESCONHECIDO", "CONTEUDO SEM REGRA CLASSIFICAVEL."])
        return path, "image/png"

    if kind == "ambiguous_ocr":
        path = case_dir / "ambiguous.png"
        _render_png(
            path,
            ["DADO AMBIGUO", "CODIGO O0I1 B8S5", "REVISAO HUMANA OBRIGATORIA."],
            blur=0.5,
        )
        return path, "image/png"

    raise ValueError(f"kind não suportado: {kind}")


def _fingerprint(texto: str, candidatos: list[CandidatoDemanda], paginas: int) -> str:
    payload = {
        "pages": paginas,
        "text_sha256": hashlib.sha256(_normalizar(texto).encode("utf-8")).hexdigest(),
        "candidates": [
            {
                "type": c.tipo,
                "page": c.pagina,
                "confidence": c.confianca,
                "human": c.requer_validacao_humana,
            }
            for c in candidatos
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _avaliar_execucao(caso: dict, arquivo: Path, content_type: str) -> tuple[dict, list[str]]:
    motor = TesseractDocumento(
        idioma="por",
        dpi_pdf=200,
        timeout_segundos=60,
        max_paginas=25,
    )
    falhas: list[str] = []
    try:
        resultado = motor.processar(arquivo, content_type=content_type)
    except FalhaOcrDocumento:
        if caso.get("expect_ocr_success", True):
            return {"expected_failure": False}, ["OCR_FAILED_UNEXPECTEDLY"]
        return {"expected_failure": True}, []

    if not caso.get("expect_ocr_success", True):
        falhas.append("OCR_SHOULD_HAVE_FAILED")

    texto_normalizado = _normalizar(resultado.texto)
    for token in caso.get("expected_tokens", []):
        if _normalizar(str(token)) not in texto_normalizado:
            falhas.append(f"TOKEN_MISSING:{token}")

    if len(resultado.paginas) < int(caso.get("min_pages", 1)):
        falhas.append("PAGE_COUNT_BELOW_EXPECTED")

    candidatos = classificar_candidatos_por_paginas(
        [(p.pagina, p.texto, p.confianca) for p in resultado.paginas]
    )
    if caso.get("expect_no_candidates") and candidatos:
        falhas.append("UNEXPECTED_CANDIDATES")
    if caso.get("must_not_auto_accept") and any(not c.requer_validacao_humana for c in candidatos):
        falhas.append("AUTO_ACCEPT_FORBIDDEN")
    if caso.get("expect_human_review") and any(not c.requer_validacao_humana for c in candidatos):
        falhas.append("CANDIDATE_WITHOUT_HUMAN_REVIEW")

    confidences = [p.confianca for p in resultado.paginas]
    fingerprint = _fingerprint(resultado.texto, candidatos, len(resultado.paginas))
    return {
        "expected_failure": False,
        "pages": len(resultado.paginas),
        "confidence_min": round(min(confidences), 6) if confidences else 0.0,
        "confidence_avg": round(sum(confidences) / len(confidences), 6) if confidences else 0.0,
        "candidates": candidatos,
        "candidate_types": tuple(sorted({c.tipo for c in candidatos})),
        "all_candidates_require_human_review": all(c.requer_validacao_humana for c in candidatos),
        "fingerprint": fingerprint,
    }, falhas


def _avaliar_caso(caso: dict, workdir: Path) -> CaseEvidence:
    arquivo, content_type = _gerar_caso(caso, workdir)
    first, failures = _avaliar_execucao(caso, arquivo, content_type)
    second, second_failures = _avaliar_execucao(caso, arquivo, content_type)
    failures.extend(second_failures)

    file_hash = _sha256(arquivo)
    expected_failure = bool(first.get("expected_failure"))
    idempotent = (
        expected_failure
        and bool(second.get("expected_failure"))
        or (
            not expected_failure
            and first.get("fingerprint") == second.get("fingerprint")
        )
    )
    if not idempotent:
        failures.append("NON_IDEMPOTENT_RESULT")

    candidatos = first.get("candidates", [])
    return CaseEvidence(
        case_id=str(caso["case_id"]),
        scenario=str(caso["scenario"]),
        file_sha256=file_hash,
        content_type=content_type,
        pages=int(first.get("pages", 1 if expected_failure else 0)),
        confidence_min=float(first.get("confidence_min", 0.0)),
        confidence_avg=float(first.get("confidence_avg", 0.0)),
        candidates=len(candidatos),
        candidate_types=tuple(first.get("candidate_types", ())),
        all_candidates_require_human_review=bool(
            first.get("all_candidates_require_human_review", True)
        ),
        idempotent=idempotent,
        outcome_fingerprint=str(first.get("fingerprint", "expected-failure")),
        status="PASS" if not failures else "FAIL",
        failures=tuple(sorted(set(failures))),
    )


def carregar_manifesto(path: Path = MANIFEST_PATH) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("schema_version inválida")
    if payload.get("contains_personal_data") is not False:
        raise ValueError("corpus v2 deve declarar ausência de dados pessoais")
    if payload.get("automatic_incorporation_allowed") is not False:
        raise ValueError("incorporação automática deve permanecer desativada")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ValueError("OCR Evidence Gate v2 exige exatamente 10 cenários")
    ids = [str(case.get("case_id") or "").strip() for case in cases]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("case_id ausente ou duplicado")
    return payload


def executar(manifest_path: Path, workdir: Path) -> dict:
    manifest = carregar_manifesto(manifest_path)
    evidencias = [_avaliar_caso(caso, workdir) for caso in manifest["cases"]]
    falhas = [e.case_id for e in evidencias if e.status != "PASS"]
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_version": manifest["corpus_version"],
        "gate": "PASS" if not falhas else "FAIL",
        "cases_total": len(evidencias),
        "cases_passed": len(evidencias) - len(falhas),
        "failed_case_ids": falhas,
        "contains_personal_data": False,
        "raw_ocr_text_published": False,
        "automatic_incorporation_allowed": False,
        "evidence": [asdict(item) for item in evidencias],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("ocr-evidence-v2.json"))
    args = parser.parse_args()

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="reqsys_ocr_evidence_v2_"))
    workdir.mkdir(parents=True, exist_ok=True)
    resultado = executar(args.manifest, workdir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {
            "gate": resultado["gate"],
            "cases_total": resultado["cases_total"],
            "cases_passed": resultado["cases_passed"],
            "failed_case_ids": resultado["failed_case_ids"],
        },
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0 if resultado["gate"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
