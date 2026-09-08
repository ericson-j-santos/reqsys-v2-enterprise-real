#!/usr/bin/env python3
"""Certificação técnica de corpus OCR público.

Reutiliza o motor OCR da aplicação e a métrica CER do certificador real, mas
nunca produz validade institucional, aprovação humana ou autorização de PROD.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from app.ocr.documento_worker import FalhaOcrDocumento, TesseractDocumento
from ocr_real_corpus_certify import character_error_rate, _normalize

DEFAULT_MAX_CER = 0.10
DEFAULT_MIN_EXACT_MATCH = 0.0


@dataclass(frozen=True)
class PublicCaseResult:
    case_id: str
    document_type: str
    file_sha256: str
    cer: float
    exact_match: bool
    status: str
    failures: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def certify_case(case: dict, corpus_root: Path, motor) -> PublicCaseResult:
    file_path = (corpus_root / str(case["file"])).resolve()
    failures: list[str] = []
    actual_hash = _sha256(file_path)
    if actual_hash != str(case.get("file_sha256") or ""):
        failures.append("SHA256_MISMATCH")
    if case.get("classification") != "PUBLIC_REFERENCE_DOCUMENT":
        failures.append("CLASSIFICATION_INVALID")
    if case.get("contains_personal_data") is not False:
        failures.append("PERSONAL_DATA_NOT_ALLOWED")
    if case.get("human_review_required") is not False:
        failures.append("PUBLIC_CORPUS_MUST_NOT_REQUIRE_HUMAN_REVIEW")

    try:
        result = motor.processar(file_path, content_type="application/pdf")
        actual = result.texto
    except FalhaOcrDocumento as exc:
        failures.append(f"OCR_FAILED:{type(exc).__name__}")
        actual = ""

    expected = str(case.get("expected") or "")
    cer = character_error_rate(expected, actual) if expected else 1.0
    exact = _normalize(expected) == _normalize(actual) if expected else False
    if cer > float(case.get("max_cer", DEFAULT_MAX_CER)):
        failures.append("CER_ABOVE_LIMIT")

    return PublicCaseResult(
        case_id=str(case.get("case_id") or ""),
        document_type=str(case.get("document_type") or "PUBLIC_DOCUMENT"),
        file_sha256=actual_hash,
        cer=cer,
        exact_match=exact,
        status="PASS" if not failures else "FAIL",
        failures=tuple(failures),
    )


def certify(manifest_path: Path, corpus_root: Path, output: Path, *, motor=None) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("corpus_type") != "public_reference":
        raise ValueError("PUBLIC_CORPUS_TYPE_REQUIRED")
    if manifest.get("institutional_validity") is not False or manifest.get("production_allowed") is not False:
        raise ValueError("PUBLIC_CORPUS_GOVERNANCE_INVALID")

    motor = motor or TesseractDocumento()
    cases = [certify_case(case, corpus_root.resolve(), motor) for case in manifest.get("cases", [])]
    total = len(cases)
    passed = sum(case.status == "PASS" for case in cases)
    average_cer = round(sum(case.cer for case in cases) / total, 6) if total else 1.0
    exact_ratio = round(sum(case.exact_match for case in cases) / total, 6) if total else 0.0
    failures: list[str] = []
    if not total:
        failures.append("NO_CASES")
    if passed != total:
        failures.append("CASE_FAILURES_PRESENT")
    if average_cer > float(manifest.get("max_average_cer", DEFAULT_MAX_CER)):
        failures.append("AVERAGE_CER_ABOVE_LIMIT")
    if exact_ratio < float(manifest.get("min_exact_match", DEFAULT_MIN_EXACT_MATCH)):
        failures.append("EXACT_MATCH_BELOW_LIMIT")

    report = {
        "schema_version": "1.0.0",
        "corpus_type": "public_reference",
        "technical_gate": "PASS" if not failures else "FAIL",
        "institutional_validity": False,
        "production_allowed": False,
        "promotion_eligible": False,
        "cases_total": total,
        "cases_passed": passed,
        "average_cer": average_cer,
        "exact_match_ratio": exact_ratio,
        "failures": failures,
        "content_exposed": False,
        "cases": [asdict(case) for case in cases],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = certify(args.manifest, args.corpus_root, args.output)
    print(json.dumps({
        "technical_gate": report["technical_gate"],
        "cases_total": report["cases_total"],
        "cases_passed": report["cases_passed"],
        "average_cer": report["average_cer"],
        "exact_match_ratio": report["exact_match_ratio"],
        "institutional_validity": False,
        "production_allowed": False,
        "promotion_eligible": False,
    }, sort_keys=True))
    return 0 if report["technical_gate"] == "PASS" else 5


if __name__ == "__main__":
    raise SystemExit(main())
