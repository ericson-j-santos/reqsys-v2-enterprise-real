from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREPARE_PATH = ROOT / "scripts" / "ocr_real_corpus_prepare.py"

spec = importlib.util.spec_from_file_location("ocr_real_corpus_prepare", PREPARE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules["ocr_real_corpus_prepare"] = module
spec.loader.exec_module(module)
prepare = module


def test_preparacao_calcula_sha_sem_fabricar_aprovacao(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    secure = tmp_path / "secure"
    corpus = secure / "corpus"
    (corpus / "cpf").mkdir(parents=True)
    doc = corpus / "cpf" / "caso-001.png"
    doc.write_bytes(b"documento-controlado")
    output = secure / "manifest.json"

    report = prepare.preparar_manifesto(corpus, output, repo_root=repo)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert report["status"] == "DRAFT_REQUIRES_HUMAN_REVIEW"
    assert report["ready_for_certification"] is False
    assert report["content_exposed"] is False
    assert payload["approval_reference"] == ""
    assert payload["contains_personal_data"] is None
    assert len(payload["cases"]) == 1
    case = payload["cases"][0]
    assert case["document_type"] == "CPF"
    assert case["classification"] == "PENDING_HUMAN_REVIEW"
    assert case["expected"] == ""
    assert case["human_review_reference"] == ""
    assert case["sha256"] == hashlib.sha256(doc.read_bytes()).hexdigest()


def test_preparacao_recusa_corpus_dentro_do_repositorio(tmp_path: Path):
    repo = tmp_path / "repo"
    corpus = repo / "secure" / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "doc.png").write_bytes(b"x")
    output = tmp_path / "manifest.json"

    try:
        prepare.preparar_manifesto(corpus, output, repo_root=repo)
    except ValueError as exc:
        assert str(exc) == "CORPUS_ROOT_INSIDE_REPOSITORY"
    else:
        raise AssertionError("corpus dentro do repositório deveria ser bloqueado")


def test_preparacao_recusa_manifesto_dentro_do_repositorio(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    corpus = tmp_path / "secure" / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "doc.pdf").write_bytes(b"pdf")
    output = repo / "manifest.json"

    try:
        prepare.preparar_manifesto(corpus, output, repo_root=repo)
    except ValueError as exc:
        assert str(exc) == "MANIFEST_OUTPUT_INSIDE_REPOSITORY"
    else:
        raise AssertionError("manifesto real dentro do repositório deveria ser bloqueado")
