from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "scripts" / "ocr_real_corpus_policy.py"
CERT_PATH = ROOT / "scripts" / "ocr_real_corpus_certify.py"

for name, path in (("ocr_real_corpus_policy", POLICY_PATH), ("ocr_real_corpus_certify", CERT_PATH)):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

cert = sys.modules["ocr_real_corpus_certify"]


@dataclass(frozen=True)
class Page:
    texto: str
    confianca: float


@dataclass(frozen=True)
class Result:
    paginas: tuple[Page, ...]

    @property
    def texto(self) -> str:
        return "\n".join(item.texto for item in self.paginas)


class FakeMotor:
    def __init__(self, text: str):
        self.text = text

    def processar(self, entrada: Path, *, content_type: str):
        return Result((Page(self.text, 0.98),))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(tmp_path: Path, corpus: Path, file_name: str, expected: str, *, review=True) -> Path:
    manifest = tmp_path / "real-manifest.json"
    payload = {
        "schema_version": "1.0.0",
        "approval_reference": "HAB-OCR-APPROVAL-001",
        "contains_personal_data": False,
        "max_average_cer": 0.10,
        "min_exact_match": 0.80,
        "cases": [
            {
                "case_id": "cpf-001",
                "document_type": "CPF",
                "file": file_name,
                "sha256": _sha(corpus / file_name),
                "classification": "ANONYMIZED_APPROVED",
                "contains_personal_data": False,
                "expected": expected,
                "human_review_reference": "REV-001" if review else "",
            }
        ],
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def test_character_error_rate_identico():
    assert cert.character_error_rate("Documento aprovado", "DOCUMENTO APROVADO") == 0.0


def test_certificacao_aprova_corpus_externo_anonimizado(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    image = corpus / "cpf.png"
    image.write_bytes(b"fake-png")
    manifest = _manifest(tmp_path, corpus, image.name, "DOCUMENTO APROVADO")
    output = tmp_path / "evidence.json"

    report = cert.certify(manifest, corpus, output, motor=FakeMotor("DOCUMENTO APROVADO"))

    assert report["gate"] == "PASS"
    assert report["promotion_eligible"] is True
    assert report["cases_passed"] == 1
    assert report["exact_match_ratio"] == 1.0
    assert report["average_cer"] == 0.0
    assert report["content_exposed"] is False
    serialized = output.read_text(encoding="utf-8")
    assert "DOCUMENTO APROVADO" not in serialized


def test_certificacao_bloqueia_sem_revisao_humana(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    image = corpus / "cpf.png"
    image.write_bytes(b"fake-png")
    manifest = _manifest(tmp_path, corpus, image.name, "DOCUMENTO APROVADO", review=False)
    output = tmp_path / "evidence.json"

    report = cert.certify(manifest, corpus, output, motor=FakeMotor("DOCUMENTO APROVADO"))

    assert report["gate"] == "FAIL"
    assert report["promotion_eligible"] is False
    assert "HUMAN_REVIEW_INCOMPLETE" in report["failures"]


def test_certificacao_bloqueia_hash_incorreto(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    image = corpus / "cpf.png"
    image.write_bytes(b"fake-png")
    manifest = _manifest(tmp_path, corpus, image.name, "DOCUMENTO APROVADO")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["cases"][0]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "evidence.json"

    report = cert.certify(manifest, corpus, output, motor=FakeMotor("DOCUMENTO APROVADO"))

    assert report["gate"] == "BLOCKED"
    assert report["promotion_eligible"] is False
    assert any("SHA256_MISMATCH" in item for item in report["policy_failures"])


def test_certificacao_bloqueia_cer_acima_do_limite(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    image = corpus / "cpf.png"
    image.write_bytes(b"fake-png")
    manifest = _manifest(tmp_path, corpus, image.name, "DOCUMENTO APROVADO")
    output = tmp_path / "evidence.json"

    report = cert.certify(manifest, corpus, output, motor=FakeMotor("TEXTO TOTALMENTE DIFERENTE"))

    assert report["gate"] == "FAIL"
    assert report["promotion_eligible"] is False
    assert "CASE_FAILURES_PRESENT" in report["failures"]
    assert "AVERAGE_CER_ABOVE_LIMIT" in report["failures"]
