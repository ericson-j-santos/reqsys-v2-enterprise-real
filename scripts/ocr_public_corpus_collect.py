#!/usr/bin/env python3
"""Coleta corpus OCR público de fontes governadas.

Baixa somente HTTPS de domínios permitidos, calcula SHA-256, extrai texto de
referência com pdftotext e gera manifesto técnico. Este caminho nunca produz
evidência institucional nem autoriza produção.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

MAX_BYTES = 25 * 1024 * 1024
SAFE_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def _allowed(hostname: str, domains: list[str]) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in domains)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_case_id(value: object) -> str:
    case_id = str(value or "").strip()
    if not SAFE_CASE_ID.fullmatch(case_id):
        raise ValueError("PUBLIC_CASE_ID_INVALID")
    return case_id


def _destination_for(output_root: Path, case_id: str) -> Path:
    root = output_root.resolve()
    destination = (root / f"{case_id}.pdf").resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ValueError("PUBLIC_OUTPUT_PATH_OUTSIDE_ROOT") from exc
    return destination


def _download(url: str, destination: Path, allowed_domains: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not _allowed(parsed.hostname or "", allowed_domains):
        raise ValueError(f"SOURCE_NOT_ALLOWED:{url}")
    request = urllib.request.Request(url, headers={"User-Agent": "ReqSys-OCR-Public-Corpus/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - allowlist enforced above
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "pdf" not in content_type and not parsed.path.lower().endswith(".pdf"):
            raise ValueError(f"SOURCE_NOT_PDF:{url}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError(f"SOURCE_TOO_LARGE:{url}")
                handle.write(chunk)
    if destination.stat().st_size == 0:
        raise ValueError(f"SOURCE_EMPTY:{url}")


def _extract_reference_text(pdf: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"REFERENCE_TEXT_EXTRACTION_FAILED:{pdf.name}")
    text = proc.stdout.strip()
    if not text:
        raise RuntimeError(f"REFERENCE_TEXT_EMPTY:{pdf.name}")
    return text


def collect(config_path: Path, output_root: Path, manifest_path: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    domains = list(config.get("allowed_domains") or [])
    sources = list(config.get("sources") or [])
    if not domains or not sources:
        raise ValueError("PUBLIC_CORPUS_CONFIG_EMPTY")

    validated_sources: list[tuple[dict, str, str]] = []
    case_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("PUBLIC_SOURCE_INVALID")
        case_id = _validate_case_id(source.get("case_id"))
        if case_id in case_ids:
            raise ValueError("PUBLIC_CASE_ID_DUPLICATED")
        case_ids.add(case_id)
        url = str(source["url"]).strip()
        validated_sources.append((source, case_id, url))

    cases = []
    for source, case_id, url in validated_sources:
        filename = f"{case_id}.pdf"
        file_path = _destination_for(output_root, case_id)
        _download(url, file_path, domains)
        expected = _extract_reference_text(file_path)
        cases.append({
            "case_id": case_id,
            "document_type": str(source.get("document_type") or "PUBLIC_DOCUMENT").upper(),
            "authority": source.get("authority"),
            "file": filename,
            "source_url": url,
            "file_sha256": _sha256(file_path),
            "classification": "PUBLIC_REFERENCE_DOCUMENT",
            "contains_personal_data": False,
            "reference_text_method": "embedded_pdf_text",
            "expected": expected,
            "human_review_required": False,
        })

    manifest = {
        "schema_version": "1.0.0",
        "corpus_type": "public_reference",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "institutional_validity": False,
        "production_allowed": False,
        "promotion_eligible": False,
        "content_exposed": False,
        "cases": cases,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = collect(args.config, args.output_root, args.manifest)
    print(json.dumps({
        "corpus_type": manifest["corpus_type"],
        "cases_total": len(manifest["cases"]),
        "institutional_validity": False,
        "production_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
