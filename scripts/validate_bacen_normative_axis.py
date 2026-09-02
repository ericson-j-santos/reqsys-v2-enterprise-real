#!/usr/bin/env python3
"""Valida o Eixo 1 normativo BACEN sem declarar conformidade.

A baseline inicial modela os 14 controles mínimos do art. 3º, § 2º, da
Resolução CMN nº 4.893/2021. O estado é derivado: obrigação sem avaliação é
`nao_avaliado`. O YAML não pode declarar `status` manualmente.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

EXPECTED_CODES = (
    "CMN4893-ART3-P2-I",
    "CMN4893-ART3-P2-II",
    "CMN4893-ART3-P2-III",
    "CMN4893-ART3-P2-IV",
    "CMN4893-ART3-P2-V",
    "CMN4893-ART3-P2-VI",
    "CMN4893-ART3-P2-VII",
    "CMN4893-ART3-P2-VIII",
    "CMN4893-ART3-P2-IX",
    "CMN4893-ART3-P2-X",
    "CMN4893-ART3-P2-XI",
    "CMN4893-ART3-P2-XII",
    "CMN4893-ART3-P2-XIII",
    "CMN4893-ART3-P2-XIV",
)
VALID_APPLICABILITY = {"pending_decision", "applicable", "not_applicable"}
REQUIRED_OBLIGATION_FIELDS = {"uid", "code", "title", "source", "introduced_by", "mapping", "assessment"}


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("baseline normativa deve ser um objeto YAML")
    return payload


def derive_state(obligation: dict[str, Any]) -> str:
    """Deriva o estado inicial sem aceitar declaração manual de status."""
    if obligation.get("assessment") is None:
        return "nao_avaliado"
    raise ValueError(
        f"{obligation.get('code', 'UNKNOWN')}: assessment não nulo ainda não é suportado pelo schema 1.0.0"
    )


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("axis") != "normative":
        errors.append("axis deve ser 'normative'")
    if payload.get("mode") != "advisory":
        errors.append("mode deve permanecer 'advisory'")

    baseline = payload.get("normative_baseline")
    if not isinstance(baseline, dict):
        errors.append("normative_baseline ausente ou inválida")
        baseline = {}

    for field in ("uid", "as_of", "regulations"):
        if not baseline.get(field):
            errors.append(f"normative_baseline.{field} ausente")

    regulations = baseline.get("regulations") or []
    references = {
        item.get("reference")
        for item in regulations
        if isinstance(item, dict)
    }
    for required_reference in ("CMN 4.893/2021", "CMN 5.274/2025"):
        if required_reference not in references:
            errors.append(f"regulação obrigatória ausente da baseline: {required_reference}")

    applicability = payload.get("applicability")
    if not isinstance(applicability, dict):
        errors.append("applicability ausente ou inválida")
        applicability = {}
    decision = applicability.get("decision")
    if decision not in VALID_APPLICABILITY:
        errors.append(f"applicability.decision inválida: {decision}")
    if decision == "not_applicable":
        if not applicability.get("decided_by") or not applicability.get("decided_at") or not applicability.get("rationale"):
            errors.append("not_applicable exige decided_by, decided_at e rationale")

    obligations = payload.get("obligations")
    if not isinstance(obligations, list) or not obligations:
        errors.append("obligations ausente ou vazia")
        obligations = []

    uids: set[str] = set()
    codes: set[str] = set()
    derived_states: dict[str, str] = {}

    for item in obligations:
        if not isinstance(item, dict):
            errors.append("obrigação inválida: item não é objeto")
            continue
        code = str(item.get("code") or "UNKNOWN")
        missing = sorted(REQUIRED_OBLIGATION_FIELDS - item.keys())
        if missing:
            errors.append(f"{code}: campos ausentes: {', '.join(missing)}")

        if "status" in item:
            errors.append(f"{code}: status não pode ser campo de entrada; deve ser derivado")

        uid = item.get("uid")
        if not isinstance(uid, str) or not uid.startswith("norm-"):
            errors.append(f"{code}: uid inválido")
        elif uid in uids:
            errors.append(f"{code}: uid duplicado: {uid}")
        else:
            uids.add(uid)

        if code in codes:
            errors.append(f"{code}: code duplicado")
        codes.add(code)

        source = item.get("source")
        if not isinstance(source, dict):
            errors.append(f"{code}: source inválido")
        else:
            if source.get("regulation") != "CMN-4893-2021":
                errors.append(f"{code}: source.regulation deve ser CMN-4893-2021")
            if source.get("article") != "3" or source.get("paragraph") != "2":
                errors.append(f"{code}: source deve apontar para art. 3º, § 2º")

        introduced = item.get("introduced_by")
        if not isinstance(introduced, dict) or introduced.get("regulation") != "CMN-5274-2025":
            errors.append(f"{code}: introduced_by deve apontar para CMN-5274-2025")

        mapping = item.get("mapping")
        if not isinstance(mapping, dict):
            errors.append(f"{code}: mapping inválido")
            mapping = {}
        refs = list(mapping.get("corporate_refs") or []) + list(mapping.get("implementation_refs") or [])
        if decision == "applicable" and not refs:
            errors.append(f"{code}: obrigação aplicável sem vínculo aos eixos 2 ou 3")

        try:
            derived_states[code] = derive_state(item)
        except ValueError as exc:
            errors.append(str(exc))

    missing_codes = sorted(set(EXPECTED_CODES) - codes)
    unexpected_codes = sorted(codes - set(EXPECTED_CODES))
    if missing_codes:
        errors.append("controles mínimos normativos ausentes: " + ", ".join(missing_codes))
    if unexpected_codes:
        warnings.append("códigos adicionais fora do escopo inicial: " + ", ".join(unexpected_codes))

    nao_avaliado = sum(state == "nao_avaliado" for state in derived_states.values())
    if nao_avaliado:
        warnings.append(
            f"{nao_avaliado} obrigação(ões) permanece(m) nao_avaliado; isso não representa conformidade parcial"
        )

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "axis": "normative",
        "baseline_uid": baseline.get("uid"),
        "as_of": baseline.get("as_of"),
        "summary": {
            "obligations_modeled": len(obligations),
            "required_minimum_controls": len(EXPECTED_CODES),
            "derived_nao_avaliado": nao_avaliado,
            "applicability_decision": decision,
            "coverage_scalar_published": False,
        },
        "derived_states": derived_states,
        "errors": errors,
        "warnings": warnings,
        "result": "invalid" if errors else "valid_with_pending_items" if warnings else "valid",
    }


def validate(path: Path) -> dict[str, Any]:
    return validate_payload(load_yaml(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="governance/bacen/normative/NORMATIVE-BASELINE.yaml")
    parser.add_argument("--output", default="artifacts/bacen/bacen-normative-axis-check.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    baseline_path = root / args.baseline
    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not baseline_path.exists():
        report: dict[str, Any] = {"result": "invalid", "errors": [f"baseline ausente: {args.baseline}"]}
    else:
        report = validate(baseline_path)

    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", report), ensure_ascii=False))
    return 1 if report.get("result") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
