#!/usr/bin/env python3
"""Descoberta/certificação OCR one-shot no Noteri sem publicar conteúdo bruto."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
from pathlib import Path
from typing import Iterable

from ocr_real_corpus_certify import certify
from ocr_real_corpus_policy import validar_corpus
from ocr_real_corpus_prepare import preparar_manifesto

SUPPORTED = {".png", ".jpg", ".jpeg", ".pdf", ".tif", ".tiff"}
HINTS = ("ocr", "corpus", "dataset", "documentos-ocr", "documentos_ocr")
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "appdata",
    "windows", "program files", "program files (x86)", "programdata",
    "$recycle.bin", "system volume information",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _path_fingerprint(path: Path) -> str:
    return hashlib.sha256(os.path.normcase(str(path.resolve())).encode("utf-8")).hexdigest()


def _add(items: list[tuple[str, Path]], label: str, path: str | Path | None) -> None:
    if not path:
        return
    p = Path(path).expanduser()
    try:
        p = p.resolve()
    except OSError:
        return
    key = os.path.normcase(str(p))
    if any(os.path.normcase(str(existing)) == key for _, existing in items):
        return
    items.append((label, p))


def standard_roots() -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for name in ("OCR_REAL_CORPUS_ROOT", "REQSYS_OCR_CORPUS_ROOT"):
        _add(items, f"env:{name}", os.getenv(name))

    local = os.getenv("LOCALAPPDATA")
    user = os.getenv("USERPROFILE")
    onedrive = os.getenv("OneDrive") or os.getenv("OneDriveConsumer")
    if local:
        _add(items, "localappdata:reqsys-ocr-real", Path(local) / "ReqSys" / "OCRRealCorpus")
        _add(items, "localappdata:reqsys-ocr", Path(local) / "ReqSys" / "OCR" / "RealCorpus")
    if user:
        home = Path(user)
        for sub, label in (("Documents", "documents"), ("Desktop", "desktop"), ("Downloads", "downloads")):
            base = home / sub
            _add(items, f"{label}:ocr-real", base / "OCRRealCorpus")
            _add(items, f"{label}:ocr", base / "OCR")
    if onedrive:
        base = Path(onedrive)
        _add(items, "onedrive:ocr-real", base / "OCRRealCorpus")
        _add(items, "onedrive:ocr", base / "OCR")

    for label, value in (
        ("c:ocr-real", r"C:\OCRRealCorpus"),
        ("c:ocr-corpus", r"C:\OCR\RealCorpus"),
        ("c:secure-ocr", r"C:\secure\ocr"),
        ("c:dev-ocr-real", r"C:\dev\ocr-real-corpus"),
        ("d:ocr-real", r"D:\OCRRealCorpus"),
        ("d:ocr-corpus", r"D:\OCR\RealCorpus"),
    ):
        _add(items, label, value)
    return items


def scan_bases() -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    user = os.getenv("USERPROFILE")
    onedrive = os.getenv("OneDrive") or os.getenv("OneDriveConsumer")
    if user:
        home = Path(user)
        for sub, label in (("Documents", "user-documents"), ("Desktop", "user-desktop"), ("Downloads", "user-downloads")):
            _add(items, label, home / sub)
    if onedrive:
        _add(items, "onedrive", onedrive)
    _add(items, "c-dev", r"C:\dev")
    _add(items, "d-dev", r"D:\dev")
    _add(items, "d-root", r"D:\")
    return [(label, path) for label, path in items if path.is_dir()]


def _looks_like_manifest(name: str) -> bool:
    low = name.casefold()
    return low in {"manifest.json", "manifest-draft.json", "ocr-real-corpus-manifest.json"} or (
        low.endswith(".json") and "manifest" in low and ("ocr" in low or "corpus" in low)
    )


def discover_hinted_roots(base: Path, label: str, *, max_depth: int = 6, max_dirs: int = 20000) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    stack: list[tuple[Path, int]] = [(base, 0)]
    visited = 0
    while stack and visited < max_dirs:
        current, depth = stack.pop()
        visited += 1
        try:
            entries = list(current.iterdir())
        except OSError:
            continue

        current_name = current.name.casefold()
        has_hint = any(hint in current_name for hint in HINTS)
        has_manifest = any(item.is_file() and _looks_like_manifest(item.name) for item in entries)
        if has_hint or has_manifest:
            found.append((f"discovered:{label}", current))

        if depth >= max_depth:
            continue
        for child in entries:
            try:
                if not child.is_dir():
                    continue
            except OSError:
                continue
            if child.name.casefold() in SKIP_DIRS:
                continue
            stack.append((child, depth + 1))
    return found


def _walk(root: Path, max_depth: int = 5):
    if not root.is_dir():
        return
    base_depth = len(root.parts)
    stack = [root]
    while stack:
        current = stack.pop()
        yield current
        if len(current.parts) - base_depth >= max_depth:
            continue
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for child in children:
            try:
                is_dir = child.is_dir()
            except OSError:
                continue
            if is_dir and child.name.casefold() not in SKIP_DIRS:
                stack.append(child)


def manifest_candidates(root: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for directory in _walk(root, 5) or []:
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for item in entries:
            if not item.is_file() or not _looks_like_manifest(item.name):
                continue
            key = os.path.normcase(str(item))
            if key not in seen:
                seen.add(key)
                found.append(item)
    return found


def document_count(root: Path, limit: int = 100000) -> int:
    count = 0
    for directory in _walk(root, 6) or []:
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for item in entries:
            try:
                is_file = item.is_file()
            except OSError:
                continue
            if is_file and item.suffix.casefold() in SUPPORTED:
                count += 1
                if count >= limit:
                    return count
    return count


def corpus_options(root: Path, manifest: Path | None = None) -> list[Path]:
    result: list[Path] = []
    for candidate in (
        manifest.parent / "corpus" if manifest else None,
        manifest.parent if manifest else None,
        root / "corpus",
        root,
    ):
        if candidate is None:
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved not in result and resolved.is_dir():
            result.append(resolved)
    return result


def all_candidate_roots() -> list[tuple[str, Path]]:
    items = standard_roots()
    for label, base in scan_bases():
        for found_label, path in discover_hinted_roots(base, label):
            _add(items, found_label, path)
    return [(label, root) for label, root in items if root.is_dir()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence: dict = {
        "schema_version": "1.1.0",
        "host": socket.gethostname(),
        "correlation_id": os.getenv("CORRELATION_ID") or "",
        "source_sha": os.getenv("GITHUB_SHA") or "",
        "content_exposed": False,
        "production_touched": False,
        "state": "NO_REAL_CORPUS_FOUND",
    }
    if evidence["host"].casefold() != "noteri":
        evidence.update(state="BLOCKED_WRONG_HOST", blocker="EXPECTED_NOTERI")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 2

    roots = all_candidate_roots()
    fingerprints: list[dict] = []
    blocked_manifests: list[dict] = []
    best: tuple[str, Path, int] | None = None

    for label, root in roots:
        docs = document_count(root)
        manifests = manifest_candidates(root)
        fingerprints.append({
            "source_label": label,
            "path_sha256": _path_fingerprint(root),
            "documents_count": docs,
            "manifest_count": len(manifests),
        })
        for manifest in manifests:
            for corpus in corpus_options(root, manifest):
                policy = validar_corpus(manifest, corpus)
                if policy.get("allowed") is True:
                    local = Path(os.getenv("LOCALAPPDATA") or str(root)) / "ReqSys" / "OCRRealCorpus"
                    report_path = local / "ocr-real-corpus-certification.json"
                    report = certify(manifest, corpus, report_path)
                    evidence.update(
                        state="CERTIFIED",
                        candidate_root_count=len(roots),
                        candidate_fingerprints=fingerprints[:50],
                        source_label=label,
                        source_path_sha256=_path_fingerprint(root),
                        manifest_sha256=_sha256(manifest),
                        gate=report.get("gate"),
                        promotion_eligible=bool(report.get("promotion_eligible")),
                        cases_total=report.get("cases_total", 0),
                        cases_passed=report.get("cases_passed", 0),
                        average_cer=report.get("average_cer"),
                        exact_match_ratio=report.get("exact_match_ratio"),
                        failures=report.get("failures", []),
                        local_report_written=True,
                    )
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    return 0
                blocked_manifests.append({
                    "source_label": label,
                    "source_path_sha256": _path_fingerprint(root),
                    "manifest_sha256": _sha256(manifest),
                    "failures": policy.get("failures", []),
                    "cases": policy.get("cases", 0),
                })
        if docs and (best is None or docs > best[2]):
            best = (label, root, docs)

    evidence.update(
        candidate_root_count=len(roots),
        candidate_fingerprints=fingerprints[:50],
    )

    if best is not None:
        label, corpus, count = best
        local = Path(os.getenv("LOCALAPPDATA") or str(corpus)) / "ReqSys" / "OCRRealCorpus"
        draft_path = local / "manifest-draft.json"
        prepared = preparar_manifesto(corpus, draft_path)
        evidence.update(
            state="DRAFT_PREPARED",
            source_label=label,
            source_path_sha256=_path_fingerprint(corpus),
            documents_found=count,
            draft_cases=prepared.get("cases", 0),
            local_manifest_draft_written=True,
            ready_for_certification=False,
            required_human_fields=prepared.get("required_human_fields", []),
        )
    elif blocked_manifests:
        evidence.update(state="BLOCKED_POLICY", blocked_manifests=blocked_manifests[:20])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
