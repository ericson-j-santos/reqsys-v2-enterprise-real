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
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import yaml
from pypdf import PdfReader, __version__ as pypdf_version

try:
    from scripts.validate_bacen_normative_axis import normalized_text_sha256, normalize_bcb_text
except ModuleNotFoundError:  # execução direta: python scripts/capture_bacen_reference_hashes.py
    from validate_bacen_normative_axis import normalized_text_sha256, normalize_bcb_text

USER_AGENT = "ReqSys-BACEN-Normative-Capture/1.0 (+https://github.com/ericson-j-santos/reqsys-v2-enterprise-real)"


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self._blocked += 1
        elif not self._blocked and tag.casefold() in {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "td", "th"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"} and self._blocked:
            self._blocked -= 1
        elif not self._blocked and tag.casefold() in {"p", "div", "li", "h1", "h2", "h3", "h4", "td", "th"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._blocked:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: YAML deve ser objeto")
    return payload


def fetch_bytes(url: str, timeout: int = 45) -> tuple[bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        },
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        data = response.read()
        content_type = response.headers.get_content_type()
    if not data:
        raise ValueError(f"fonte vazia: {url}")
    return data, content_type


def extract_pdf_text(data: bytes) -> tuple[str, dict[str, Any]]:
    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n".join(pages)
    if not text.strip():
        raise ValueError("PDF sem texto extraível")
    return text, {"parser": "pypdf", "parser_version": pypdf_version, "pages": len(reader.pages)}


def extract_html_section(data: bytes, capture: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    html = data.decode("utf-8", errors="replace")
    parser = VisibleTextParser()
    parser.feed(html)
    text = normalize_bcb_text(parser.text())
    start_marker = str(capture.get("start_marker") or "")
    end_marker = str(capture.get("end_marker") or "")
    if start_marker:
        start = text.casefold().find(start_marker.casefold())
        if start < 0:
            raise ValueError(f"marcador inicial não encontrado: {start_marker}")
        text = text[start:]
    if end_marker:
        end = text.casefold().find(end_marker.casefold())
        if end < 0:
            raise ValueError(f"marcador final não encontrado: {end_marker}")
        text = text[: end + len(end_marker)]
    return text, {"parser": "html-visible-text-v1"}


def validate_markers(text: str, markers: list[str], uid: str) -> None:
    folded = text.casefold()
    missing = [marker for marker in markers if marker.casefold() not in folded]
    if missing:
        raise ValueError(f"{uid}: marcadores esperados ausentes: {', '.join(missing)}")


def capture_document(doc: dict[str, Any]) -> dict[str, Any]:
    uid = str(doc.get("uid") or "UNKNOWN")
    capture = doc.get("capture")
    if not isinstance(capture, dict):
        raise ValueError(f"{uid}: bloco capture ausente")
    kind = str(capture.get("kind") or "")
    source = str(capture.get("source") or doc.get("official_source") or "")
    if not source.startswith("https://"):
        raise ValueError(f"{uid}: fonte de captura deve usar HTTPS")

    data, content_type = fetch_bytes(source)
    if kind == "pdf_text":
        text, metadata = extract_pdf_text(data)
    elif kind == "html_section":
        text, metadata = extract_html_section(data, capture)
    else:
        raise ValueError(f"{uid}: capture.kind não suportado: {kind}")

    normalized = normalize_bcb_text(text)
    markers = [str(item) for item in capture.get("expected_markers") or []]
    validate_markers(normalized, markers, uid)
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
        "capture_source": source,
        "source_content_type": content_type,
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
        "schema_version": "1.0.0",
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
