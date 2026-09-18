#!/usr/bin/env python3
"""Captura hashes SHA-256 de referências técnicas do BCB sobre texto normalizado.

Os documentos brutos são mantidos apenas em memória. A identidade primária continua
sendo versão + data de publicação; o hash é um detector auxiliar de alteração.
"""
from __future__ import annotations

import argparse
import io
import json
import ssl
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pypdf import PdfReader, __version__ as pypdf_version

try:
    from scripts.validate_bacen_normative_axis import normalized_text_sha256, normalize_bcb_text
except ModuleNotFoundError:  # execução direta
    from validate_bacen_normative_axis import normalized_text_sha256, normalize_bcb_text

USER_AGENT = "ReqSys-BACEN-Normative-Capture/1.1 (+https://github.com/ericson-j-santos/reqsys-v2-enterprise-real)"


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: YAML deve ser objeto")
    return payload


def fetch_bytes(url: str, timeout: int = 60) -> tuple[bytes, str]:
    if not url.startswith("https://"):
        raise ValueError(f"fonte deve usar HTTPS: {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*;q=0.5"},
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        data = response.read()
        content_type = response.headers.get_content_type()
    if not data:
        raise ValueError(f"fonte vazia: {url}")
    return data, content_type


def extract_pdf_text(data: bytes) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if not text.strip():
        raise ValueError("PDF sem texto extraível")
    return text, len(reader.pages)


def validate_markers(text: str, markers: list[str], uid: str) -> None:
    folded = text.casefold()
    missing = [marker for marker in markers if marker.casefold() not in folded]
    if missing:
        raise ValueError(f"{uid}: marcadores esperados ausentes: {', '.join(missing)}")


def capture_single_pdf(capture: dict[str, Any], uid: str) -> tuple[str, dict[str, Any]]:
    source = str(capture.get("source") or "")
    data, content_type = fetch_bytes(source)
    text, pages = extract_pdf_text(data)
    normalized = normalize_bcb_text(text)
    validate_markers(normalized, [str(item) for item in capture.get("expected_markers") or []], uid)
    return normalized, {
        "capture_source": source,
        "source_content_type": content_type,
        "parser": "pypdf",
        "parser_version": pypdf_version,
        "pages": pages,
    }


def capture_pdf_set(capture: dict[str, Any], uid: str) -> tuple[str, dict[str, Any]]:
    sources = capture.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"{uid}: pdf_text_set requer sources não vazio")

    normalized_members: list[str] = []
    member_evidence: list[dict[str, Any]] = []
    total_pages = 0
    for index, member in enumerate(sources, start=1):
        if not isinstance(member, dict):
            raise ValueError(f"{uid}: membro {index} inválido")
        member_uid = str(member.get("uid") or f"member-{index}")
        source = str(member.get("source") or "")
        data, content_type = fetch_bytes(source)
        text, pages = extract_pdf_text(data)
        normalized = normalize_bcb_text(text)
        validate_markers(normalized, [str(item) for item in member.get("expected_markers") or []], f"{uid}/{member_uid}")
        normalized_members.append(normalized)
        total_pages += pages
        member_evidence.append(
            {
                "uid": member_uid,
                "source": source,
                "content_type": content_type,
                "pages": pages,
                "normalized_chars": len(normalized),
                "normalized_sha256": normalized_text_sha256(normalized),
            }
        )

    combined = normalize_bcb_text("\n\n".join(normalized_members))
    validate_markers(combined, [str(item) for item in capture.get("expected_markers") or []], uid)
    return combined, {
        "capture_source": [item["source"] for item in member_evidence],
        "source_content_type": "application/pdf-set",
        "parser": "pypdf-set",
        "parser_version": pypdf_version,
        "pages": total_pages,
        "members": member_evidence,
    }


def capture_document(doc: dict[str, Any]) -> dict[str, Any]:
    uid = str(doc.get("uid") or "UNKNOWN")
    capture = doc.get("capture")
    if not isinstance(capture, dict):
        raise ValueError(f"{uid}: bloco capture ausente")
    kind = str(capture.get("kind") or "")

    if kind == "pdf_text":
        normalized, metadata = capture_single_pdf(capture, uid)
    elif kind == "pdf_text_set":
        normalized, metadata = capture_pdf_set(capture, uid)
    else:
        raise ValueError(f"{uid}: capture.kind não suportado: {kind}")

    sha256 = normalized_text_sha256(normalized)
    expected = doc.get("content_sha256")
    state = doc.get("hash_state")
    match = expected == sha256 if state == "captured" else None

    return {
        "uid": uid,
        "title": doc.get("title"),
        "version": doc.get("version"),
        "published_at": doc.get("published_at"),
        "capture_kind": kind,
        "capture_scope": capture.get("scope"),
        "normalization_profile": doc.get("normalization_profile"),
        "normalized_chars": len(normalized),
        "content_sha256": sha256,
        "baseline_hash_state": state,
        "baseline_content_sha256": expected,
        "matches_baseline": match,
        **metadata,
    }


def run(baseline_path: Path, verify: bool) -> dict[str, Any]:
    payload = load_yaml(baseline_path)
    baseline = payload.get("normative_baseline") or {}
    docs = baseline.get("referenced_documents") or []
    if not isinstance(docs, list) or not docs:
        raise ValueError("referenced_documents ausente")

    results = [capture_document(doc) for doc in docs]
    mismatches = [item["uid"] for item in results if item.get("matches_baseline") is False]
    uncaptured = [item["uid"] for item in results if item.get("baseline_hash_state") != "captured"]
    report = {
        "schema_version": "1.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline_uid": baseline.get("uid"),
        "documents": results,
        "summary": {
            "documents": len(results),
            "captured_in_baseline": len(results) - len(uncaptured),
            "pending_in_baseline": len(uncaptured),
            "mismatches": len(mismatches),
        },
        "mismatches": mismatches,
        "pending_in_baseline": uncaptured,
        "result": "mismatch" if mismatches else "captured_with_pending_baseline" if uncaptured else "verified",
    }
    if verify and (mismatches or uncaptured):
        report["result"] = "invalid"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="governance/bacen/normative/NORMATIVE-BASELINE-V2.yaml")
    parser.add_argument("--output", default="artifacts/bacen/bacen-reference-hashes.json")
    parser.add_argument("--verify", action="store_true", help="falha se houver hash pendente ou divergente")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    report = run(root / args.baseline, args.verify)
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 1 if report["result"] == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
