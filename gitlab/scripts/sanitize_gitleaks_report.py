#!/usr/bin/env python3
"""Sanitize a redacted Gitleaks JSON report for safe CI diagnosis.

Only rule identifier, repository-relative path and line numbers leave this
process. Secret, Match, Entropy, Fingerprint, commit/author metadata and all
other source fields are deliberately discarded.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "1.0.0"
RULE_ID_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,160}$")
FORBIDDEN_OUTPUT_KEYS = {
    "Secret",
    "Match",
    "Entropy",
    "Fingerprint",
    "Commit",
    "Author",
    "Email",
    "Message",
    "Date",
}


class SanitizationError(RuntimeError):
    """Raised when the input cannot be safely reduced to diagnostic metadata."""


def _safe_rule_id(value: Any) -> str:
    rule_id = str(value or "").strip()
    if not RULE_ID_RE.fullmatch(rule_id):
        raise SanitizationError("invalid_rule_id")
    return rule_id


def _safe_path(value: Any) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    if not raw or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise SanitizationError("invalid_file_path")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise SanitizationError("unsafe_file_path")
    normalized = str(path)
    if normalized in {".", ""}:
        raise SanitizationError("invalid_file_path")
    return normalized


def _safe_line(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise SanitizationError(f"invalid_{field}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SanitizationError(f"invalid_{field}") from exc
    if number < 1:
        raise SanitizationError(f"invalid_{field}")
    return number


def sanitize_finding(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise SanitizationError("finding_not_object")
    start = _safe_line(item.get("StartLine"), "start_line")
    end = _safe_line(item.get("EndLine", start), "end_line")
    if end < start:
        raise SanitizationError("end_line_before_start_line")
    return {
        "RuleID": _safe_rule_id(item.get("RuleID")),
        "File": _safe_path(item.get("File")),
        "StartLine": start,
        "EndLine": end,
    }


def sanitize_report(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, list):
        raise SanitizationError("report_not_list")
    findings = [sanitize_finding(item) for item in payload]
    findings.sort(key=lambda item: (item["File"], item["StartLine"], item["EndLine"], item["RuleID"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "finding_count": len(findings),
        "findings": findings,
        "redaction_contract": {
            "emitted_fields": ["RuleID", "File", "StartLine", "EndLine"],
            "sensitive_fields_emitted": [],
        },
    }


def render_log_lines(summary: dict[str, Any]) -> list[str]:
    lines = [f"GITLEAKS_SANITIZED_COUNT={summary['finding_count']}"]
    for finding in summary["findings"]:
        # JSON encoding plus control-character rejection prevents log injection.
        lines.append(
            "GITLEAKS_SANITIZED_FINDING="
            + json.dumps(finding, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
    return lines


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix="gitleaks-summary-", suffix=".json", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sanitize Gitleaks report metadata")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        summary = sanitize_report(payload)
        serialized = json.dumps(summary, ensure_ascii=False)
        if any(key in serialized for key in FORBIDDEN_OUTPUT_KEYS):
            raise SanitizationError("forbidden_output_key")
        _atomic_write_json(args.output, summary)
    except (OSError, json.JSONDecodeError, SanitizationError) as exc:
        print(f"GITLEAKS_SANITIZER_BLOCKED={type(exc).__name__}:{exc}")
        return 2

    if args.print_summary:
        for line in render_log_lines(summary):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
