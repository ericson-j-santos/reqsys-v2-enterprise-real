#!/usr/bin/env python3
"""Valida a matriz mínima de controles BACEN e gera evidência auditável."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_CONTROL_FIELDS = {
    "id",
    "domain",
    "title",
    "criticality",
    "owner",
    "evidence",
    "status",
    "review_cycle_days",
}
VALID_STATUS = {"implemented", "partial", "gap", "not_applicable"}
VALID_CRITICALITY = {"critical", "high", "medium", "low"}


def parse_controls(text: str) -> list[dict[str, str]]:
    controls: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^- id:\s*(.+)$", line)
        if match:
            if current:
                controls.append(current)
            current = {"id": match.group(1).strip()}
            continue
        if current and ":" in line and not line.startswith("-"):
            key, value = line.split(":", 1)
            current[key.strip()] = value.strip().strip('"\'')
    if current:
        controls.append(current)
    return controls


def canonical_manifest_path(root: Path, evidence: str) -> Path | None:
    evidence_path = Path(evidence)
    if evidence_path.parts[:2] != ("artifacts", "bacen"):
        return None
    return root / "governance" / "bacen" / "evidence" / f"{evidence_path.stem}.manifest.yaml"


def parse_simple_yaml(text: str) -> dict[str, str]:
    """Lê apenas pares escalares de primeiro nível do manifesto canônico."""
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if raw_line.startswith((" ", "\t")):
            continue
        result[key.strip()] = value.strip().strip('"\'')
    return result


def resolve_evidence(root: Path, control_id: str, evidence: str) -> tuple[dict[str, str], list[str]]:
    evidence_file = root / evidence
    if evidence_file.exists():
        return {
            "control_id": control_id,
            "declared_evidence": evidence,
            "resolution": "materialized_artifact",
            "resolved_path": evidence,
        }, []

    manifest = canonical_manifest_path(root, evidence)
    if manifest is None or not manifest.exists():
        return {
            "control_id": control_id,
            "declared_evidence": evidence,
            "resolution": "not_materialized",
            "resolved_path": "",
        }, [f"{control_id}: evidência ainda não materializada: {evidence}"]

    manifest_data = parse_simple_yaml(manifest.read_text(encoding="utf-8"))
    findings: list[str] = []
    if manifest_data.get("control_id") != control_id:
        findings.append(f"{control_id}: manifesto canônico possui control_id divergente")
    if manifest_data.get("artifact_path") != evidence:
        findings.append(f"{control_id}: manifesto canônico não referencia o artifact declarado")
    if manifest_data.get("evidence_status") not in {"canonical_reference", "materialized"}:
        findings.append(f"{control_id}: manifesto canônico possui evidence_status inválido")

    resolution = "canonical_manifest" if not findings else "invalid_canonical_manifest"
    return {
        "control_id": control_id,
        "declared_evidence": evidence,
        "resolution": resolution,
        "resolved_path": str(manifest.relative_to(root)),
    }, findings


def validate(root: Path, matrix_path: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    evidence_resolution: list[dict[str, str]] = []
    controls = parse_controls(matrix_path.read_text(encoding="utf-8"))
    ids: set[str] = set()

    if not controls:
        errors.append("A matriz não contém controles.")

    for control in controls:
        control_id = control.get("id", "UNKNOWN")
        missing = sorted(REQUIRED_CONTROL_FIELDS - control.keys())
        if missing:
            errors.append(f"{control_id}: campos ausentes: {', '.join(missing)}")
        if control_id in ids:
            errors.append(f"{control_id}: identificador duplicado")
        ids.add(control_id)
        if control.get("status") not in VALID_STATUS:
            errors.append(f"{control_id}: status inválido: {control.get('status')}")
        if control.get("criticality") not in VALID_CRITICALITY:
            errors.append(f"{control_id}: criticidade inválida: {control.get('criticality')}")
        evidence = control.get("evidence")
        if evidence:
            resolution, findings = resolve_evidence(root, control_id, evidence)
            evidence_resolution.append(resolution)
            if resolution["resolution"] == "invalid_canonical_manifest":
                errors.extend(findings)
            else:
                warnings.extend(findings)

    critical_gaps = [
        c["id"] for c in controls
        if c.get("criticality") == "critical" and c.get("status") == "gap"
    ]
    coverage = round(
        100 * sum(c.get("status") == "implemented" for c in controls) / len(controls), 2
    ) if controls else 0.0

    return {
        "schema_version": "1.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "advisory",
        "summary": {
            "total_controls": len(controls),
            "implemented": sum(c.get("status") == "implemented" for c in controls),
            "partial": sum(c.get("status") == "partial" for c in controls),
            "gaps": sum(c.get("status") == "gap" for c in controls),
            "critical_gaps": critical_gaps,
            "implemented_coverage_percent": coverage,
            "canonical_evidence_resolved": sum(
                item["resolution"] == "canonical_manifest" for item in evidence_resolution
            ),
            "evidence_not_materialized": sum(
                item["resolution"] == "not_materialized" for item in evidence_resolution
            ),
        },
        "evidence_resolution": evidence_resolution,
        "errors": errors,
        "warnings": warnings,
        "result": "invalid" if errors else "valid_with_gaps" if critical_gaps else "valid",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="governance/bacen/BACEN-CONTROL-MATRIX.yaml")
    parser.add_argument("--output", default="artifacts/bacen/bacen-controls-report.json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    matrix = root / args.matrix
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    if not matrix.exists():
        report = {"result": "invalid", "errors": [f"Matriz ausente: {args.matrix}"]}
    else:
        report = validate(root, matrix)

    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"] if "summary" in report else report, ensure_ascii=False))

    if report.get("result") == "invalid":
        return 1
    if args.strict and report.get("summary", {}).get("critical_gaps"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
