from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL_CERT_PATH = ROOT / "scripts" / "ocr_real_corpus_certify.py"
PUBLIC_CERT_PATH = ROOT / "scripts" / "ocr_public_corpus_certify.py"

for name, path in (("ocr_real_corpus_certify", REAL_CERT_PATH), ("ocr_public_corpus_certify", PUBLIC_CERT_PATH)):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

cert = sys.modules["ocr_public_corpus_certify"]


@dataclass(frozen=True)
class Result:
    texto: str


class FakeMotor:
    def __init__(self, text: str):
        self.text = text

    def processar(self, entrada: Path, *, content_type: str):
        return Result(self.text)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(tmp_path: Path, corpus: Path, expected: str) -> Path:
    pdf = corpus / "public.pdf"
    payload = {
        "schema_version": "1.0.0",
        "corpus_type": "public_reference",
        "institutional_validity": False,
        "production_allowed": False,
        "max_average_cer": 0.10,
        "min_exact_match": 0.50,
        "cases": [{
            "case_id": "public-001",
            "document_type": "RELATORIO_PUBLICO",
            "file": pdf.name,
            "file_sha256": _sha(pdf),
            "classification": "PUBLIC_REFERENCE_DOCUMENT",
            "contains_personal_data": False,
            "human_review_required": False,
            "expected": expected,
        }],
    }
    manifest = tmp_path / "public-manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def test_public_corpus_passa_tecnicamente_sem_autorizar_producao(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "public.pdf").write_bytes(b"fake-pdf")
    manifest = _manifest(tmp_path, corpus, "DOCUMENTO PUBLICO")
    output = tmp_path / "report.json"

    report = cert.certify(manifest, corpus, output, motor=FakeMotor("DOCUMENTO PUBLICO"))

    assert report["technical_gate"] == "PASS"
    assert report["institutional_validity"] is False
    assert report["production_allowed"] is False
    assert report["promotion_eligible"] is False
    assert report["cases_passed"] == 1
    assert "DOCUMENTO PUBLICO" not in output.read_text(encoding="utf-8")


def test_public_corpus_falha_hash_sem_converter_em_evidencia_institucional(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "public.pdf").write_bytes(b"fake-pdf")
    manifest = _manifest(tmp_path, corpus, "DOCUMENTO PUBLICO")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["cases"][0]["file_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "report.json"

    report = cert.certify(manifest, corpus, output, motor=FakeMotor("DOCUMENTO PUBLICO"))

    assert report["technical_gate"] == "FAIL"
    assert report["promotion_eligible"] is False
    assert "CASE_FAILURES_PRESENT" in report["failures"]
