#!/usr/bin/env python3
"""Valida o Eixo 1 normativo BACEN sem declarar conformidade.

A baseline v2 compõe a fotografia v1 (14 controles mínimos) com obrigações
adicionais materiais introduzidas pela CMN 5.274/2025. Status continua derivado.
Documentos vivos usam version + published_at como identidade primária e SHA-256
do texto normalizado apenas como detector auxiliar de divergência.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

MINIMUM_CODES = tuple(f"CMN4893-ART3-P2-{item}" for item in (
    "I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV"
))
EXTENDED_CODES = (
    ("CMN4893-ART3-P6",)
    + tuple(f"CMN4893-ART3-P7-{item}" for item in ("I","II","III"))
    + tuple(f"CMN4893-ART3-P8-{item}" for item in ("I","II","III","IV","V"))
    + tuple(f"CMN4893-ART3-P9-{item}" for item in ("I","II","III"))
    + tuple(f"CMN4893-ART3-P10-{item}" for item in ("I","II","III","IV"))
    + tuple(f"CMN4893-ART3-P11-{item}" for item in ("I","II","III","IV","V","VI"))
    + tuple(f"CMN4893-ART3-P12-{item}" for item in ("I","II","III","IV"))
    + tuple(f"CMN4893-ART3A-I-{item}" for item in ("A","B","C","D","E","F"))
    + ("CMN4893-ART3A-II",)
    + tuple(f"CMN4893-ART3A-PU-{item}" for item in ("I","II","III"))
    + tuple(f"CMN4893-ART22A-{item}" for item in ("I","II","III"))
    + ("CMN4893-ART22B-CAPUT","CMN4893-ART22B-P1","CMN4893-ART22B-P2","CMN4893-ART23-X")
)
EXPECTED_CODES = MINIMUM_CODES + EXTENDED_CODES
VALID_APPLICABILITY = {"pending_decision", "applicable", "not_applicable"}
VALID_HASH_STATE = {"pending_initial_capture", "captured"}
PAGE_MARKER = re.compile(r"^(?:p[aá]gina\s+)?\d+\s*/\s*\d+$|^page\s+\d+(?:\s+of\s+\d+)?$", re.I)
KNOWN_HEADER_PREFIXES = ("manual de segurança do sfn", "manual de redes do sfn", "catálogo de serviços do sfn")


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: conteúdo YAML deve ser objeto")
    return payload


def normalize_bcb_text(text: str) -> str:
    """Perfil bcb-text-v1: NFKC, LF, whitespace canônico e ruído paginado removido."""
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    counts = Counter(line.casefold() for line in lines if line)
    normalized: list[str] = []
    for line in lines:
        if not line:
            continue
        folded = line.casefold()
        if PAGE_MARKER.fullmatch(line):
            continue
        if counts[folded] >= 3 and folded.startswith(KNOWN_HEADER_PREFIXES):
            continue
        normalized.append(line)
    return "\n".join(normalized).strip() + "\n"


def normalized_text_sha256(text: str) -> str:
    return hashlib.sha256(normalize_bcb_text(text).encode("utf-8")).hexdigest()


def derive_state(obligation: dict[str, Any]) -> str:
    if obligation.get("assessment") is None:
        return "nao_avaliado"
    raise ValueError(f"{obligation.get('code','UNKNOWN')}: assessment não nulo ainda não suportado")


def load_obligation_sets(root: Path, baseline: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    obligations: list[dict[str, Any]] = []
    for ref in baseline.get("obligation_sets") or []:
        if not isinstance(ref, dict) or not ref.get("path"):
            errors.append("obligation_set inválido")
            continue
        path = root / str(ref["path"])
        if not path.exists():
            errors.append(f"obligation_set ausente: {ref['path']}")
            continue
        doc = load_yaml(path)
        items = doc.get(str(ref.get("selector") or "obligations"))
        if not isinstance(items, list):
            errors.append(f"{ref['path']}: selector não resolve lista")
            continue
        expected = ref.get("expected_count")
        if isinstance(expected, int) and len(items) != expected:
            errors.append(f"{ref['path']}: esperado {expected}, encontrado {len(items)}")
        obligations.extend(items)
    return obligations, errors


def validate_referenced_documents(baseline: dict[str, Any], as_of: str | None) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    docs = baseline.get("referenced_documents") or []
    if not isinstance(docs, list) or len(docs) < 3:
        errors.append("referenced_documents deve modelar Catálogo, Manual de Redes e Manual de Segurança")
        docs = []

    uids: set[str] = set()
    captured = 0
    pending = 0
    as_of_date = None
    if as_of:
        try:
            as_of_date = datetime.fromisoformat(as_of.replace("Z", "+00:00")).date()
        except ValueError:
            errors.append("normative_baseline.as_of inválido")

    for doc in docs:
        if not isinstance(doc, dict):
            errors.append("referenced_document inválido")
            continue
        uid = doc.get("uid")
        for field in ("uid","title","version","published_at","checked_at","official_source","hash_scope","normalization_profile","hash_state"):
            if doc.get(field) in (None, ""):
                errors.append(f"{uid or 'UNKNOWN'}: {field} ausente")
        if uid in uids:
            errors.append(f"{uid}: uid duplicado em referenced_documents")
        if uid:
            uids.add(str(uid))
        if doc.get("hash_scope") != "normalized_text":
            errors.append(f"{uid}: hash_scope deve ser normalized_text; hash de PDF bruto é proibido")
        if doc.get("normalization_profile") != "bcb-text-v1":
            errors.append(f"{uid}: normalization_profile deve ser bcb-text-v1")
        state = doc.get("hash_state")
        if state not in VALID_HASH_STATE:
            errors.append(f"{uid}: hash_state inválido: {state}")
        value = doc.get("content_sha256")
        if state == "captured":
            captured += 1
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                errors.append(f"{uid}: content_sha256 capturado deve conter 64 hex minúsculos")
        elif state == "pending_initial_capture":
            pending += 1
            if value not in (None, ""):
                errors.append(f"{uid}: pending_initial_capture exige content_sha256 nulo")
            warnings.append(f"{uid}: hash normalizado inicial ainda não capturado; Gate 2 deve permanecer bloqueado")

        cycle = doc.get("check_cycle_days")
        checked = doc.get("checked_at")
        if as_of_date and isinstance(cycle, int) and isinstance(checked, str):
            try:
                age = (as_of_date - date.fromisoformat(checked)).days
                if age > cycle:
                    warnings.append(f"{uid}: checked_at fora da janela de {cycle} dias")
            except ValueError:
                errors.append(f"{uid}: checked_at inválido")

    return errors, warnings, {"referenced_documents": len(docs), "hash_captured": captured, "hash_pending": pending}


def validate_payload(payload: dict[str, Any], obligations: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("axis") != "normative":
        errors.append("axis deve ser normative")
    if payload.get("mode") != "advisory":
        errors.append("mode deve permanecer advisory")

    baseline = payload.get("normative_baseline")
    if not isinstance(baseline, dict):
        errors.append("normative_baseline ausente ou inválida")
        baseline = {}
    for field in ("uid","as_of","regulations","obligation_sets","hash_policy"):
        if not baseline.get(field):
            errors.append(f"normative_baseline.{field} ausente")

    hash_policy = baseline.get("hash_policy") or {}
    if hash_policy.get("primary_identity") != ["version", "published_at"]:
        errors.append("hash_policy.primary_identity deve ser [version, published_at]")
    if hash_policy.get("hash_scope") != "normalized_text":
        errors.append("hash_policy.hash_scope deve ser normalized_text")
    if hash_policy.get("content_hash_role") != "auxiliary_change_detector":
        errors.append("content_sha256 deve permanecer detector auxiliar, não identidade primária")

    applicability = payload.get("applicability")
    if not isinstance(applicability, dict):
        errors.append("applicability ausente")
        applicability = {}
    decision = applicability.get("decision")
    if decision not in VALID_APPLICABILITY:
        errors.append(f"applicability.decision inválida: {decision}")
    if decision == "not_applicable" and not all(applicability.get(k) for k in ("decided_by","decided_at","rationale")):
        errors.append("not_applicable exige decided_by, decided_at e rationale")

    uids: set[str] = set()
    codes: set[str] = set()
    derived: dict[str, str] = {}
    for item in obligations:
        if not isinstance(item, dict):
            errors.append("obrigação inválida")
            continue
        code = str(item.get("code") or "UNKNOWN")
        if "status" in item:
            errors.append(f"{code}: status não pode ser campo de entrada")
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
        if not item.get("title") or not isinstance(item.get("source"), dict):
            errors.append(f"{code}: title/source ausente")
        mapping = item.get("mapping")
        if not isinstance(mapping, dict):
            errors.append(f"{code}: mapping inválido")
            mapping = {}
        refs = list(mapping.get("corporate_refs") or []) + list(mapping.get("implementation_refs") or [])
        if decision == "applicable" and not refs:
            errors.append(f"{code}: obrigação aplicável sem vínculo aos eixos 2 ou 3")
        try:
            derived[code] = derive_state(item)
        except ValueError as exc:
            errors.append(str(exc))

    missing = sorted(set(EXPECTED_CODES) - codes)
    unexpected = sorted(codes - set(EXPECTED_CODES))
    if missing:
        errors.append("obrigações normativas esperadas ausentes: " + ", ".join(missing))
    if unexpected:
        warnings.append("códigos adicionais fora do escopo v2: " + ", ".join(unexpected))

    doc_errors, doc_warnings, doc_summary = validate_referenced_documents(baseline, baseline.get("as_of"))
    errors.extend(doc_errors)
    warnings.extend(doc_warnings)

    nao_avaliado = sum(v == "nao_avaliado" for v in derived.values())
    if nao_avaliado:
        warnings.append(f"{nao_avaliado} obrigação(ões) permanecem nao_avaliado")

    return {
        "schema_version": "2.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "advisory",
        "axis": "normative",
        "baseline_uid": baseline.get("uid"),
        "as_of": baseline.get("as_of"),
        "summary": {
            "obligations_modeled": len(obligations),
            "minimum_controls": len(MINIMUM_CODES),
            "extended_obligations": len(EXTENDED_CODES),
            "expected_total": len(EXPECTED_CODES),
            "derived_nao_avaliado": nao_avaliado,
            "applicability_decision": decision,
            "coverage_scalar_published": False,
            **doc_summary,
        },
        "derived_states": derived,
        "errors": errors,
        "warnings": warnings,
        "result": "invalid" if errors else "valid_with_pending_items" if warnings else "valid",
    }


def validate(path: Path) -> dict[str, Any]:
    payload = load_yaml(path)
    root = path.resolve().parents[3]
    baseline = payload.get("normative_baseline") or {}
    obligations, load_errors = load_obligation_sets(root, baseline)
    report = validate_payload(payload, obligations)
    if load_errors:
        report["errors"] = load_errors + list(report["errors"])
        report["result"] = "invalid"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="governance/bacen/normative/NORMATIVE-BASELINE-V2.yaml")
    parser.add_argument("--output", default="artifacts/bacen/bacen-normative-axis-check.json")
    parser.add_argument("--hash-text-file", default=None)
    args = parser.parse_args()

    if args.hash_text_file:
        text = Path(args.hash_text_file).read_text(encoding="utf-8")
        print(normalized_text_sha256(text))
        return 0

    root = Path(__file__).resolve().parents[1]
    baseline_path = root / args.baseline
    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = validate(baseline_path) if baseline_path.exists() else {"result":"invalid","errors":[f"baseline ausente: {args.baseline}"]}
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", report), ensure_ascii=False))
    return 1 if report.get("result") == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
