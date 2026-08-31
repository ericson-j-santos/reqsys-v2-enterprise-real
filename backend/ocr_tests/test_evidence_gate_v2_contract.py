from pathlib import Path
import importlib.util
import sys

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ocr_evidence_gate_v2.py"
spec = importlib.util.spec_from_file_location("ocr_evidence_gate_v2", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_manifesto_v2_cobre_os_dez_cenarios_governados():
    payload = mod.carregar_manifesto()
    kinds = {case["kind"] for case in payload["cases"]}
    assert kinds == {
        "searchable_pdf",
        "scanned_pdf",
        "multi_document_pdf",
        "rotated_image",
        "low_resolution_image",
        "mobile_photo_image",
        "identity_proof_bundle",
        "blank_page",
        "unknown_document",
        "ambiguous_ocr",
    }


def test_manifesto_v2_proibe_pii_real_e_incorporacao_automatica():
    payload = mod.carregar_manifesto()
    assert payload["contains_personal_data"] is False
    assert payload["automatic_incorporation_allowed"] is False


def test_caso_de_identidade_declara_somente_identificadores_sinteticos():
    payload = mod.carregar_manifesto()
    case = next(item for item in payload["cases"] if item["kind"] == "identity_proof_bundle")
    assert case["synthetic_identifiers_only"] is True
    assert set(case["expected_tokens"]) >= {"CPF", "RG", "CIN", "CNH", "COMPROVANTE"}


def test_pagina_sem_conteudo_exige_falha_fechada():
    payload = mod.carregar_manifesto()
    case = next(item for item in payload["cases"] if item["kind"] == "blank_page")
    assert case["expect_ocr_success"] is False
    assert case["expected_failure"] == "NO_USABLE_TEXT"


def test_evidencia_publicada_nao_tem_campo_de_texto_ocr_bruto():
    fields = set(mod.CaseEvidence.__dataclass_fields__)
    assert "texto" not in fields
    assert "raw_text" not in fields
    assert "file_sha256" in fields
    assert "outcome_fingerprint" in fields
