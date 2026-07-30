#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TARGET_SECTIONS = {
    "Resumo executivo": 120,
    "Incidentes de segurança do período": 120,
    "Avaliação de terceiros e nuvem": 120,
    "Plano de ação para o próximo ciclo": 120,
}
PLACEHOLDER_PATTERNS = (
    re.compile(r"\*\(seção narrativa", re.IGNORECASE),
    re.compile(r"\bpreencher\b", re.IGNORECASE),
    re.compile(r"\bpendente\b", re.IGNORECASE),
    re.compile(r"ainda não existe", re.IGNORECASE),
    re.compile(r"deve ser preenchid[ao]", re.IGNORECASE),
)
HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def extract_sections(text: str) -> tuple[dict[str, str], list[str]]:
    matches = list(HEADING_PATTERN.finditer(text))
    sections: dict[str, str] = {}
    duplicates: list[str] = []
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if heading in sections:
            duplicates.append(heading)
        else:
            sections[heading] = body
    return sections, duplicates


def meaningful_length(body: str) -> int:
    cleaned = re.sub(r"<!--.*?-->", " ", body, flags=re.DOTALL)
    cleaned = re.sub(r"[`*_>#|\-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return len(cleaned)


def build_report(report_path: Path) -> dict[str, Any]:
    report_text = report_path.read_text(encoding="utf-8")
    sections, duplicate_headings = extract_sections(report_text)
    missing_sections: list[str] = []
    pending_sections: list[str] = []
    evaluated: list[dict[str, Any]] = []

    for heading, minimum_chars in TARGET_SECTIONS.items():
        body = sections.get(heading)
        if body is None:
            missing_sections.append(heading)
            evaluated.append(
                {
                    "section": heading,
                    "present": False,
                    "minimum_meaningful_chars": minimum_chars,
                    "meaningful_chars": 0,
                    "placeholder_detected": False,
                    "narrative_ready": False,
                }
            )
            continue

        placeholder_detected = any(pattern.search(body) for pattern in PLACEHOLDER_PATTERNS)
        chars = meaningful_length(body)
        ready = chars >= minimum_chars and not placeholder_detected
        if not ready:
            pending_sections.append(heading)
        evaluated.append(
            {
                "section": heading,
                "present": True,
                "minimum_meaningful_chars": minimum_chars,
                "meaningful_chars": chars,
                "placeholder_detected": placeholder_detected,
                "narrative_ready": ready,
            }
        )

    automatic_blocking = bool(missing_sections or duplicate_headings)
    ready_count = sum(1 for section in evaluated if section["narrative_ready"])
    target_count = len(TARGET_SECTIONS)
    narrative_ready = ready_count == target_count and not automatic_blocking

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-08",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "report_path": str(report_path),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "summary": {
            "target_sections": target_count,
            "ready_sections": ready_count,
            "pending_sections": target_count - ready_count,
            "coverage_percent": round(ready_count / target_count * 100, 2),
        },
        "sections": evaluated,
        "missing_sections": sorted(missing_sections),
        "duplicate_headings": sorted(set(duplicate_headings)),
        "pending_section_names": sorted(set(pending_sections)),
        "narrative_readiness_complete": narrative_ready,
        "control_status": "implemented" if narrative_ready else "partial",
        "automatic_blocking": automatic_blocking,
        "human_action_required": not narrative_ready,
        "production_touched": False,
        "next_stage": "complete_and_review_annual_report_narrative_sections",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera prontidão das seções narrativas do relatório anual BACEN-08"
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = build_report(args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence["summary"], ensure_ascii=False))
    return 1 if evidence["automatic_blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
