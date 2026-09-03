from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "governance/bacen/normative/NORMATIVE-BASELINE.yaml"
EXTENDED = ROOT / "governance/bacen/normative/NORMATIVE-OBLIGATIONS-EXTENDED.yaml"
EVIDENCE_MODEL = ROOT / "governance/bacen/normative/EVIDENCE-MODEL.yaml"
ARTIFACT = ROOT / "artifacts/bacen/bacen-structural-gate.json"

UID_RE = re.compile(r"^norm-[a-z0-9]{8,}$")
ALLOWED_DECISIONS = {"pending_decision", "applicable", "not_applicable"}
FORBIDDEN_SCALAR_KEYS = {"coverage", "coverage_percent", "compliance_percent", "regulatory_coverage"}


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def iter_obligations(*payloads: dict[str, Any]):
    for payload in payloads:
        for obligation in payload.get("obligations") or []:
            yield obligation


def has_scalar_coverage(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_SCALAR_KEYS:
                return True
            if has_scalar_coverage(child):
                return True
    elif isinstance(value, list):
        return any(has_scalar_coverage(item) for item in value)
    return False


def validate_cross_ref(ref: Any) -> bool:
    if not isinstance(ref, dict):
        return False
    required = {"repo", "ref", "path"}
    return required.issubset(ref) and all(str(ref[k]).strip() for k in required)


def validate() -> dict[str, Any]:
    base = load_yaml(BASELINE)
    extended = load_yaml(EXTENDED)
    evidence_model = load_yaml(EVIDENCE_MODEL)
    errors: list[str] = []
    warnings: list[str] = []

    obligations = list(iter_obligations(base, extended))
    if len(obligations) != 57:
        errors.append(f"R1: esperadas 57 obrigações, encontradas {len(obligations)}")

    uids: list[str] = []
    codes: list[str] = []
    for obligation in obligations:
        uid = obligation.get("uid")
        code = obligation.get("code")
        if not uid or not UID_RE.match(str(uid)):
            errors.append(f"R1/R2: uid inválido: {uid!r}")
        if not code:
            errors.append(f"R1: obrigação {uid!r} sem code")
        if "status" in obligation:
            errors.append(f"R9: obrigação {uid!r} contém status manual")
        assessment = obligation.get("assessment")
        if isinstance(assessment, dict) and "status" in assessment:
            errors.append(f"R9: assessment de {uid!r} contém status manual")
        uids.append(str(uid))
        codes.append(str(code))

    if len(set(uids)) != len(uids):
        errors.append("R1/R2: uid normativo duplicado")
    if len(set(codes)) != len(codes):
        errors.append("R1: code normativo duplicado")

    applicability = base.get("applicability") or {}
    decision = applicability.get("decision")
    if decision not in ALLOWED_DECISIONS:
        errors.append(f"R6/R12: decisão de aplicabilidade inválida: {decision!r}")
    if decision == "not_applicable":
        for field in ("decided_by", "decided_at", "rationale"):
            if not applicability.get(field):
                errors.append(f"R6/R12: not_applicable exige {field}")

    if decision == "applicable":
        for obligation in obligations:
            mapping = obligation.get("mapping") or {}
            refs = (mapping.get("corporate_refs") or []) + (mapping.get("implementation_refs") or [])
            if not refs:
                errors.append(f"R3: obrigação aplicável {obligation.get('uid')} sem vínculo aos eixos 2/3")
            for ref in refs:
                if isinstance(ref, dict) and not validate_cross_ref(ref):
                    errors.append(f"R4: referência cruzada incompleta em {obligation.get('uid')}")

    for payload_name, payload in (("baseline", base), ("extended", extended)):
        if has_scalar_coverage(payload):
            errors.append(f"R5: {payload_name} publica cobertura regulatória escalar")

    referenced_documents = ((base.get("normative_baseline") or {}).get("referenced_documents") or [])
    for doc in referenced_documents:
        for field in ("version", "published_at", "checked_at"):
            if not doc.get(field):
                errors.append(f"R7: documento {doc.get('uid') or doc.get('name')} sem {field}")
        content_identity = doc.get("content_identity") or {}
        if content_identity:
            if content_identity.get("hash_scope") != "normalized_text":
                errors.append(f"R7: documento {doc.get('uid') or doc.get('name')} sem hash_scope normalized_text")
            sha = content_identity.get("content_sha256")
            if sha and not re.fullmatch(r"[0-9a-f]{64}", str(sha)):
                errors.append(f"R13: hash inválido no documento {doc.get('uid') or doc.get('name')}")

    invariants = evidence_model.get("invariants") or {}
    expected_invariants = {
        "status_is_derived": True,
        "status_manual_input_forbidden": True,
        "as_of_required": True,
        "temporal_origin": "event_at",
        "collected_at_drives_validity": False,
        "collected_at_drives_retention": False,
        "validity_and_retention_are_independent": True,
    }
    for key, expected in expected_invariants.items():
        if invariants.get(key) != expected:
            errors.append(f"R9-R11: invariável {key} deve ser {expected!r}")

    contract = evidence_model.get("evidence_contract") or {}
    required = set(contract.get("required") or [])
    for field in ("uid", "norm_uid", "event_at", "collected_at", "sha256", "source"):
        if field not in required:
            errors.append(f"R11/R13: contrato de evidência não exige {field}")
    if "status" not in set(contract.get("forbidden") or []):
        errors.append("R9: contrato de evidência não proíbe status")

    optional = set(contract.get("optional") or [])
    if "masking" not in optional:
        errors.append("R14: contrato não prevê masking")
    if "custody_ref" not in optional:
        errors.append("R13/R14: contrato não prevê custody_ref")

    digest = hashlib.sha256()
    for path in (BASELINE, EXTENDED, EVIDENCE_MODEL):
        digest.update(path.read_bytes())

    result = {
        "schema_version": "1.0.0",
        "gate": "BACEN Structural Gate R1-R14",
        "result": "valid" if not errors else "invalid",
        "obligations": len(obligations),
        "unique_uids": len(set(uids)),
        "unique_codes": len(set(codes)),
        "applicability_decision": decision,
        "coverage_scalar_published": has_scalar_coverage(base) or has_scalar_coverage(extended),
        "status_manual_detected": any("status manual" in e for e in errors),
        "input_sha256": digest.hexdigest(),
        "errors": errors,
        "warnings": warnings,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ARTIFACT)
    args = parser.parse_args()
    result = validate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["result"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
