#!/usr/bin/env python3
"""Classifica se uma mudança exige igualdade de SHA no runtime público DEV."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

SAFE_NON_RUNTIME_PREFIXES = (
    ".github/",
    ".sdd/",
    "artifacts/",
    "audit/",
    "backend/ocr_tests/",
    "backend/tests/",
    "docs/",
    "docs-site/",
    "e2e/",
    "evidence/",
    "reports/",
    "tests/",
)

DOCUMENTATION_SUFFIXES = {".adoc", ".md", ".rst"}


def _normalize_path(raw: str) -> str | None:
    value = raw.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:/", value):
        return None
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def is_safe_non_runtime_path(path: str) -> bool:
    """Retorna true apenas para superfícies que não compõem o runtime publicado."""

    normalized = _normalize_path(path)
    if normalized is None:
        return False

    if normalized.startswith(SAFE_NON_RUNTIME_PREFIXES):
        return True

    candidate = PurePosixPath(normalized)
    return len(candidate.parts) == 1 and candidate.suffix in DOCUMENTATION_SUFFIXES


def classify_paths(
    paths: Iterable[str],
    *,
    scope_available: bool,
    event_name: str,
    base_sha: str = "",
    head_sha: str = "",
) -> dict[str, object]:
    normalized_paths: list[str] = []
    invalid_paths: list[str] = []
    for raw in paths:
        normalized = _normalize_path(raw)
        if normalized is None:
            if raw.strip():
                invalid_paths.append(raw.strip())
            continue
        normalized_paths.append(normalized)

    changed_paths = sorted(dict.fromkeys(normalized_paths))
    invalid_paths = sorted(dict.fromkeys(invalid_paths))
    runtime_paths = [path for path in changed_paths if not is_safe_non_runtime_path(path)]
    runtime_paths.extend(f"invalid:{path}" for path in invalid_paths)
    non_runtime_paths = [path for path in changed_paths if path not in runtime_paths]

    if not scope_available:
        runtime_sha_required = True
        reason = "change_scope_unavailable_fail_closed"
    elif not changed_paths and not invalid_paths:
        runtime_sha_required = True
        reason = "empty_change_scope_fail_closed"
    elif runtime_paths:
        runtime_sha_required = True
        reason = "runtime_or_unknown_path_changed"
    else:
        runtime_sha_required = False
        reason = "ci_sdd_test_or_docs_only"

    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-public-access-runtime-sha-scope",
        "event_name": event_name,
        "base_sha": base_sha.lower(),
        "head_sha": head_sha.lower(),
        "scope_available": scope_available,
        "runtime_sha_required": runtime_sha_required,
        "decision_reason": reason,
        "changed_paths": changed_paths,
        "non_runtime_paths": non_runtime_paths,
        "runtime_or_unknown_paths": runtime_paths,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--changed-files-file", type=Path, required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--scope-available", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    paths = args.changed_files_file.read_text(encoding="utf-8").splitlines()
    payload = classify_paths(
        paths,
        scope_available=args.scope_available,
        event_name=args.event_name,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
