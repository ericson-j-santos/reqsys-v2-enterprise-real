#!/usr/bin/env python3
"""Valida o mapeamento estrutural das obrigações BACEN para controles e decisões ReqSys.

O mapeamento é deliberadamente não probatório: ele não decide aplicabilidade, não
promove assessment e não transforma vínculo arquitetural em evidência regulatória.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from validate_bacen_normative_axis import EXPECTED_CODES

ALLOWED_CONTROLS = {f"BACEN-{number:02d}" for number in range(1, 9)}


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: YAML deve ser objeto")
    return payload


def group_matches(group: dict[str, Any], code: str) -> bool:
    match = group.get("match") or {}
    if isinstance(match, dict) and match.get("all") is True:
        return True
    if code in {str(item) for item in group.get("codes") or []}:
        return True
    return any(code.startswith(str(prefix)) for prefix in group.get("prefixes") or [])


def validate_mapping(root: Path, baseline_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    baseline_payload = load_yaml(baseline_path)
    baseline = baseline_payload.get("normative_baseline") or {}
    mapping_rel = baseline.get("mapping_file")
    if not mapping_rel:
        return {"result": "invalid", "errors": ["normative_baseline.mapping_file ausente"], "warnings": []}

    mapping_path = root / str(mapping_rel)
    if not mapping_path.exists():
        return {"result": "invalid", "errors": [f"mapping_file ausente: {mapping_rel}"], "warnings": []}
    payload = load_yaml(mapping_path)

    if payload.get("mode") != "structural_only":
        errors.append("mapping.mode deve ser structural_only")
    if payload.get("baseline_uid") != baseline.get("uid"):
        errors.append("mapping.baseline_uid deve coincidir com a baseline v2")
    if payload.get("evidence_claim") is not False:
        errors.append("mapping.evidence_claim deve permanecer false")
    if payload.get("assessment_promotion") is not False:
        errors.append("mapping.assessment_promotion deve permanecer false")
    semantics = payload.get("semantics") or {}
    if semantics.get("assessment_promotion") is not False:
        errors.append("semantics.assessment_promotion deve permanecer false")

    catalog = payload.get("reference_catalog") or {}
    catalog_controls = {str(item) for item in catalog.get("controls") or []}
    if catalog_controls != ALLOWED_CONTROLS:
        errors.append("reference_catalog.controls deve conter exatamente BACEN-01..08")

    path_refs = [str(item) for item in catalog.get("adrs") or []] + [str(item) for item in catalog.get("pdrs") or []]
    for ref in path_refs:
        if not (root / ref).exists():
            errors.append(f"referência ADR/PDR ausente no repositório: {ref}")

    mappings = payload.get("control_mappings")
    if not isinstance(mappings, dict):
        errors.append("control_mappings deve ser objeto")
        mappings = {}
    mapping_codes = {str(code) for code in mappings}
    expected = set(EXPECTED_CODES)
    missing = sorted(expected - mapping_codes)
    unexpected = sorted(mapping_codes - expected)
    if missing:
        errors.append("obrigações sem mapeamento de controle: " + ", ".join(missing))
    if unexpected:
        errors.append("mapeamentos para códigos fora da baseline v2: " + ", ".join(unexpected))

    for code, refs in mappings.items():
        if not isinstance(refs, list) or not refs:
            errors.append(f"{code}: control_refs vazio")
            continue
        invalid = sorted({str(ref) for ref in refs} - ALLOWED_CONTROLS)
        if invalid:
            errors.append(f"{code}: controles inválidos: {', '.join(invalid)}")
        if len({str(ref) for ref in refs}) != len(refs):
            errors.append(f"{code}: controle duplicado")

    groups = payload.get("design_link_groups")
    if not isinstance(groups, list) or not groups:
        errors.append("design_link_groups deve ser lista não vazia")
        groups = []

    all_design_refs: set[str] = set()
    effective: dict[str, dict[str, list[str]]] = {}
    for code in EXPECTED_CODES:
        adr_refs: set[str] = set()
        pdr_refs: set[str] = set()
        for group in groups:
            if not isinstance(group, dict):
                errors.append("design_link_group inválido")
                continue
            if group_matches(group, code):
                adr_refs.update(str(item) for item in group.get("adr_refs") or [])
                pdr_refs.update(str(item) for item in group.get("pdr_refs") or [])
        if not adr_refs:
            errors.append(f"{code}: sem vínculo ADR efetivo")
        if not pdr_refs:
            errors.append(f"{code}: sem vínculo PDR efetivo")
        for ref in sorted(adr_refs | pdr_refs):
            all_design_refs.add(ref)
            if not (root / ref).exists():
                errors.append(f"{code}: referência de design ausente: {ref}")
        effective[code] = {"adr_refs": sorted(adr_refs), "pdr_refs": sorted(pdr_refs)}

    if any("implemented" in str(value).casefold() or "evidenced" in str(value).casefold() for value in payload.values()):
        warnings.append("campos textuais mencionam estados; validar manualmente que não representam promoção")

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "baseline_uid": baseline.get("uid"),
        "mode": "structural_only",
        "summary": {
            "expected_obligations": len(EXPECTED_CODES),
            "mapped_obligations": len(mapping_codes & expected),
            "macrocontrols_referenced": len({ref for refs in mappings.values() if isinstance(refs, list) for ref in refs} & ALLOWED_CONTROLS),
            "design_references": len(all_design_refs),
            "assessment_promotion": False,
            "evidence_claim": False,
        },
        "effective_design_links": effective,
        "errors": errors,
        "warnings": warnings,
        "result": "invalid" if errors else "valid_with_warnings" if warnings else "valid",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="governance/bacen/normative/NORMATIVE-BASELINE-V2.yaml")
    parser.add_argument("--output", default="artifacts/bacen/bacen-normative-mapping-check.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = validate_mapping(root, root / args.baseline)
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", report), ensure_ascii=False))
    return 1 if report.get("result") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
