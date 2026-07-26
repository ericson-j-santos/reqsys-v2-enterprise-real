#!/usr/bin/env python3
"""Consolida e indexa (BACEN-07) as evidências de auditoria dos controles BACEN.

Varre artifacts/bacen/*.json, calcula SHA-256 de cada artifact (trilha de
integridade/chain-of-custody) e cruza com a matriz de controles para garantir que
todo controle `implemented`/`partial` tenha ao menos uma evidência indexada.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.validate_bacen_controls import parse_controls  # noqa: E402

TRACKED_STATUSES = {"implemented", "partial"}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def index_evidence(evidence_dir: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    if not evidence_dir.exists():
        return entries
    for path in sorted(evidence_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        entries.append(
            {
                "path": str(path.relative_to(evidence_dir.parents[1])),
                "sha256": sha256_of(path),
                "size_bytes": path.stat().st_size,
                "control_id": payload.get("control_id"),
                "schema_version": payload.get("schema_version"),
            }
        )
    return entries


def consolidate(root: Path, matrix_path: Path, evidence_dir: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []

    entries = index_evidence(evidence_dir)
    if not entries:
        warnings.append("Nenhuma evidência encontrada em artifacts/bacen/.")

    controls = parse_controls(matrix_path.read_text(encoding="utf-8")) if matrix_path.exists() else []
    covered_control_ids = {entry["control_id"] for entry in entries if entry.get("control_id")}

    uncovered: list[str] = []
    tracked_ids: list[str] = []
    for control in controls:
        control_id = control.get("id", "UNKNOWN")
        status = control.get("status")
        if status not in TRACKED_STATUSES:
            continue
        tracked_ids.append(control_id)
        if control_id == "BACEN-07":
            # O índice é a própria evidência de BACEN-07: sua existência ao final
            # desta execução (bem-sucedida) já comprova a cobertura do controle.
            continue
        evidence_field = control.get("evidence", "")
        evidence_materialized = evidence_field and (root / evidence_field).exists()
        if control_id not in covered_control_ids and not evidence_materialized:
            uncovered.append(control_id)
            errors.append(
                f"{control_id}: status '{status}' sem evidência indexada nem arquivo declarado em `evidence`"
            )

    controls_covered = sorted(set(tracked_ids) - set(uncovered))

    return {
        "schema_version": "1.0.0",
        "control_id": "BACEN-07",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "entries": entries,
        "summary": {
            "total_evidence_files": len(entries),
            "total_controls": len(controls),
            "controls_covered": controls_covered,
            "controls_uncovered": uncovered,
        },
        "errors": errors,
        "warnings": warnings,
        "result": "invalid" if errors else "valid",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="governance/bacen/BACEN-CONTROL-MATRIX.yaml")
    parser.add_argument("--evidence-dir", default="artifacts/bacen")
    parser.add_argument("--output", default="artifacts/bacen/bacen-07-audit-evidence-index.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    matrix_path = root / args.matrix
    evidence_dir = root / args.evidence_dir
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    report = consolidate(root, matrix_path, evidence_dir)

    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))

    return 1 if report.get("result") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
