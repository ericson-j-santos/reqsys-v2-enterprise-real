#!/usr/bin/env python3
"""Certificação governada de corpus OCR real/anônimo.

O corpus e o manifesto ficam fora do repositório. O relatório publicado contém
somente métricas, hashes e referências de governança; nunca texto OCR bruto.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ocr.documento_worker import FalhaOcrDocumento, TesseractDocumento
from ocr_real_corpus_policy import validar_corpus

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}

DEFAULT_MAX_CER = 0.10
DEFAULT_MIN_EXACT_MATCH = 0.80


@dataclass(frozen=True)
class CaseCertification:
    case_id: str
    document_type: str
    file_sha256: str
    pages: int
    confidence_avg: float
    cer: float
    exact_match: bool
    human_review_reference_present: bool
    status: str
    failures: tuple[str, ...]


def _normalize(text: str) -> str:
    value = "".join(
        c for c in unicodedata.normalize("NFKD", text or "")
        if not unicodedata.combining(c)
    ).upper()
    return re.sub(r"\s+", " ", value).strip()


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (ca != cb),
            ))
        previous = current
    return previous[-1]


def character_error_rate(expected: str, actual: str) -> float:
    expected_n = _normalize(expected)
    actual_n = _normalize(actual)
    if not expected_n:
        return 0.0 if not actual_n else 1.0
    return round(_levenshtein(expected_n, actual_n) / len(expected_n), 6)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def certify_case(case: dict, corpus_root: Path, motor) -> CaseCertification:
    case_id = str(case.get("case_id") or "").strip()
    document_type = str(case.get("document_type") or "UNKNOWN").strip().upper()
    file_path = (corpus_root / str(case.get("file") or "")).resolve()
    failures: list[str] = []
    review_ref = str(case.get("human_review_reference") or "").strip()
    if not review_ref:
        failures.append("HUMAN_REVIEW_REFERENCE_REQUIRED")

    content_type = CONTENT_TYPES.get(file_path.suffix.lower())
    if not content_type:
        failures.append("CONTENT_TYPE_UNSUPPORTED")
        return CaseCertification(
            case_id, document_type, _sha256(file_path), 0, 0.0, 1.0, False,
            bool(review_ref), "FAIL", tuple(failures),
        )

    try:
        result = motor.processar(file_path, content_type=content_type)
        actual = result.texto
        pages = len(result.paginas)
        confidences = [page.confianca for page in result.paginas]
        confidence_avg = round(sum(confidences) / len(confidences), 6) if confidences else 0.0
    except FalhaOcrDocumento as exc:
        failures.append(f"OCR_FAILED:{type(exc).__name__}")
        return CaseCertification(
            case_id, document_type, _sha256(file_path), 0, 0.0, 1.0, False,
            bool(review_ref), "FAIL", tuple(failures),
        )

    expected = str(case.get("expected") or "")
    cer = character_error_rate(expected, actual)
    exact = _normalize(expected) == _normalize(actual)
    max_cer = float(case.get("max_cer", DEFAULT_MAX_CER))
    if cer > max_cer:
        failures.append("CER_ABOVE_LIMIT")

    return CaseCertification(
        case_id=case_id,
        document_type=document_type,
        file_sha256=_sha256(file_path),
        pages=pages,
        confidence_avg=confidence_avg,
        cer=cer,
        exact_match=exact,
        human_review_reference_present=bool(review_ref),
        status="PASS" if not failures else "FAIL",
        failures=tuple(failures),
    )


def certify(manifest_path: Path, corpus_root: Path, output: Path, *, motor=None) -> dict:
    policy = validar_corpus(manifest_path, corpus_root)
    if not policy["allowed"]:
        report = {
            "schema_version": "1.0.0",
            "gate": "BLOCKED",
            "promotion_eligible": False,
            "policy_failures": policy["failures"],
            "content_exposed": False,
            "cases": [],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return report

    manifest = _load_manifest(manifest_path)
    motor = motor or TesseractDocumento()
    evidence = [certify_case(case, corpus_root.resolve(), motor) for case in manifest["cases"]]

    total = len(evidence)
    passed = sum(item.status == "PASS" for item in evidence)
    exact_total = sum(item.exact_match for item in evidence)
    exact_ratio = round(exact_total / total, 6) if total else 0.0
    average_cer = round(sum(item.cer for item in evidence) / total, 6) if total else 1.0
    max_average_cer = float(manifest.get("max_average_cer", DEFAULT_MAX_CER))
    min_exact_match = float(manifest.get("min_exact_match", DEFAULT_MIN_EXACT_MATCH))

    by_type: dict[str, dict[str, float | int]] = {}
    for item in evidence:
        bucket = by_type.setdefault(item.document_type, {"cases": 0, "passed": 0, "cer_sum": 0.0})
        bucket["cases"] += 1
        bucket["passed"] += int(item.status == "PASS")
        bucket["cer_sum"] += item.cer
    for bucket in by_type.values():
        cases = int(bucket["cases"])
        bucket["average_cer"] = round(float(bucket.pop("cer_sum")) / cases, 6) if cases else 1.0

    failures: list[str] = []
    if passed != total:
        failures.append("CASE_FAILURES_PRESENT")
    if average_cer > max_average_cer:
        failures.append("AVERAGE_CER_ABOVE_LIMIT")
    if exact_ratio < min_exact_match:
        failures.append("EXACT_MATCH_BELOW_LIMIT")
    if any(not item.human_review_reference_present for item in evidence):
        failures.append("HUMAN_REVIEW_INCOMPLETE")

    report = {
        "schema_version": "1.0.0",
        "gate": "PASS" if not failures else "FAIL",
        "promotion_eligible": not failures,
        "approval_reference": manifest.get("approval_reference"),
        "cases_total": total,
        "cases_passed": passed,
        "average_cer": average_cer,
        "exact_match_ratio": exact_ratio,
        "thresholds": {
            "max_average_cer": max_average_cer,
            "min_exact_match": min_exact_match,
        },
        "by_document_type": by_type,
        "failures": failures,
        "content_exposed": False,
        "cases": [asdict(item) for item in evidence],
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
        "gate": report["gate"],
        "promotion_eligible": report.get("promotion_eligible", False),
        "cases_total": report.get("cases_total", 0),
        "cases_passed": report.get("cases_passed", 0),
        "average_cer": report.get("average_cer"),
        "exact_match_ratio": report.get("exact_match_ratio"),
        "failures": report.get("failures", report.get("policy_failures", [])),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("promotion_eligible") else 5


if __name__ == "__main__":
    raise SystemExit(main())
