from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_COLLECT_PATH = ROOT / "scripts" / "ocr_public_corpus_collect.py"
PUBLIC_CERT_PATH = ROOT / "scripts" / "ocr_public_corpus_certify.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


collector = _load_module("ocr_public_corpus_collect", PUBLIC_COLLECT_PATH)
cert = _load_module("ocr_public_corpus_certify", PUBLIC_CERT_PATH)


@dataclass(frozen=True)
class Result:
    texto: str


class FakeMotor:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def processar(self, entrada: Path, *, content_type: str):
        self.calls += 1
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


def test_public_corpus_bloqueia_path_traversal_sem_ler_arquivo_externo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "public.pdf").write_bytes(b"fake-pdf")
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    manifest = _manifest(tmp_path, corpus, "DOCUMENTO PUBLICO")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["cases"][0]["file"] = "../outside.pdf"
    payload["cases"][0]["file_sha256"] = _sha(outside)
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "report.json"
    motor = FakeMotor("DOCUMENTO PUBLICO")

    def forbidden_hash(_: Path) -> str:
        raise AssertionError("arquivo externo não deve ser lido")

    monkeypatch.setattr(cert, "_sha256", forbidden_hash)
    report = cert.certify(manifest, corpus, output, motor=motor)

    assert report["technical_gate"] == "FAIL"
    assert report["promotion_eligible"] is False
    assert report["cases"][0]["file_sha256"] == ""
    assert "UNSAFE_FILE_PATH" in report["cases"][0]["failures"]
    assert motor.calls == 0


def test_public_corpus_bloqueia_link_simbolico_para_fora_da_raiz(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    (corpus / "public.pdf").symlink_to(outside)
    manifest = _manifest(tmp_path, corpus, "DOCUMENTO PUBLICO")
    output = tmp_path / "report.json"
    motor = FakeMotor("DOCUMENTO PUBLICO")

    report = cert.certify(manifest, corpus, output, motor=motor)

    assert report["technical_gate"] == "FAIL"
    assert "PATH_OUTSIDE_CORPUS_ROOT" in report["cases"][0]["failures"]
    assert report["cases"][0]["file_sha256"] == ""
    assert motor.calls == 0


@pytest.mark.parametrize(
    "case_ids, expected_error",
    [
        (["../escape"], "PUBLIC_CASE_ID_INVALID"),
        (["public-001", "public-001"], "PUBLIC_CASE_ID_DUPLICATED"),
    ],
)
def test_public_collector_valida_todos_os_ids_antes_de_baixar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_ids: list[str],
    expected_error: str,
):
    config = tmp_path / "sources.json"
    config.write_text(
        json.dumps({
            "allowed_domains": ["example.com"],
            "sources": [
                {"case_id": case_id, "url": "https://example.com/document.pdf"}
                for case_id in case_ids
            ],
        }),
        encoding="utf-8",
    )
    downloads = 0

    def forbidden_download(*_args, **_kwargs):
        nonlocal downloads
        downloads += 1

    monkeypatch.setattr(collector, "_download", forbidden_download)

    with pytest.raises(ValueError, match=expected_error):
        collector.collect(config, tmp_path / "corpus", tmp_path / "manifest.json")

    assert downloads == 0
