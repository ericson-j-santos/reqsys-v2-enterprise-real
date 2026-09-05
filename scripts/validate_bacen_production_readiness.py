#!/usr/bin/env python3
"""Gate 2 BACEN: prontidão normativa e institucional para promoção a produção.

O gate não bloqueia desenvolvimento, homologação ou a branch main por dívida
institucional. A mesma avaliação informa `would_block_production`, mas só é
enforçada quando o estágio alvo é PRODUCTION e o chamador solicita `--enforce`.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

try:
    from scripts.bacen_derived_status import derive_status, parse_utc, validate_evidence
    from scripts.validate_bacen_production_gate import evaluate_gate as evaluate_formal_gate
except ImportError:  # execução direta a partir de scripts/
    from bacen_derived_status import derive_status, parse_utc, validate_evidence
    from validate_bacen_production_gate import evaluate_gate as evaluate_formal_gate

PRODUCTION_STAGE = "PRODUCTION"
NON_PRODUCTION_ALIASES = {
    "DEV": "DEVELOPMENT",
    "DEVELOPMENT": "DEVELOPMENT",
    "HML": "STAGING",
    "HOMOLOG": "STAGING",
    "HOMOLOGATION": "STAGING",
    "STAGING": "STAGING",
}
PRODUCTION_ALIASES = {"PROD": PRODUCTION_STAGE, PRODUCTION_STAGE: PRODUCTION_STAGE}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} deve conter um objeto YAML")
    return payload


def normalize_stage(value: str) -> str:
    stage = str(value or "").strip().upper()
    if stage in PRODUCTION_ALIASES:
        return PRODUCTION_ALIASES[stage]
    if stage in NON_PRODUCTION_ALIASES:
        return NON_PRODUCTION_ALIASES[stage]
    raise ValueError(f"estágio alvo inválido: {value!r}")


def _parse_date(value: Any, *, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field} deve usar YYYY-MM-DD") from exc


def _obligations(*payloads: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for payload in payloads:
        obligations = payload.get("obligations") or []
        if not isinstance(obligations, list):
            raise ValueError("obligations deve ser lista")
        items.extend(item for item in obligations if isinstance(item, dict))
    return items


def _family_applicability_blockers(applicability: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    decision = str(applicability.get("decision") or "").strip()
    if decision == "pending_decision" or not decision:
        blockers.append(
            {
                "code": "family_applicability_pending",
                "scope": applicability.get("family") or "regulatory_family",
                "reason": "aplicabilidade institucional ainda não foi decidida formalmente",
            }
        )
        return "pending_decision", blockers
    if decision not in {"applicable", "not_applicable"}:
        blockers.append(
            {
                "code": "family_applicability_invalid",
                "scope": applicability.get("family") or "regulatory_family",
                "reason": f"decisão de aplicabilidade inválida: {decision!r}",
            }
        )
        return decision, blockers
    if decision == "not_applicable":
        missing = [field for field in ("decided_by", "decided_at", "rationale") if not applicability.get(field)]
        if missing:
            blockers.append(
                {
                    "code": "family_not_applicable_incomplete",
                    "scope": applicability.get("family") or "regulatory_family",
                    "reason": "decisão not_applicable incompleta",
                    "missing_fields": missing,
                }
            )
        elif applicability.get("decided_at"):
            try:
                parse_utc(str(applicability["decided_at"]))
            except ValueError as exc:
                blockers.append(
                    {
                        "code": "family_not_applicable_invalid_timestamp",
                        "scope": applicability.get("family") or "regulatory_family",
                        "reason": str(exc),
                    }
                )
    return decision, blockers


def _registry_indexes(
    registry: dict[str, Any],
    known_uids: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    applicability_items = registry.get("applicability_decisions") or []
    evidence_items = registry.get("evidences") or []
    if not isinstance(applicability_items, list):
        raise ValueError("applicability_decisions deve ser lista")
    if not isinstance(evidence_items, list):
        raise ValueError("evidences deve ser lista")

    applicability_by_uid: dict[str, dict[str, Any]] = {}
    for item in applicability_items:
        if not isinstance(item, dict):
            blockers.append({"code": "invalid_applicability_entry", "reason": "entrada deve ser objeto"})
            continue
        norm_uid = str(item.get("norm_uid") or "")
        if norm_uid not in known_uids:
            blockers.append(
                {
                    "code": "unknown_applicability_norm_uid",
                    "norm_uid": norm_uid,
                    "reason": "decisão de aplicabilidade referencia obrigação desconhecida",
                }
            )
            continue
        if norm_uid in applicability_by_uid:
            blockers.append(
                {
                    "code": "duplicate_applicability_decision",
                    "norm_uid": norm_uid,
                    "reason": "mais de uma decisão de aplicabilidade para a mesma obrigação",
                }
            )
            continue
        applicability_by_uid[norm_uid] = item

    evidence_by_uid: dict[str, list[dict[str, Any]]] = {uid: [] for uid in known_uids}
    seen_evidence_uids: set[str] = set()
    for item in evidence_items:
        if not isinstance(item, dict):
            blockers.append({"code": "invalid_evidence_entry", "reason": "evidência deve ser objeto"})
            continue
        evidence_uid = str(item.get("uid") or "")
        norm_uid = str(item.get("norm_uid") or "")
        if evidence_uid in seen_evidence_uids:
            blockers.append(
                {
                    "code": "duplicate_evidence_uid",
                    "evidence_uid": evidence_uid,
                    "reason": "uid de evidência duplicado",
                }
            )
            continue
        seen_evidence_uids.add(evidence_uid)
        if norm_uid not in known_uids:
            blockers.append(
                {
                    "code": "unknown_evidence_norm_uid",
                    "evidence_uid": evidence_uid,
                    "norm_uid": norm_uid,
                    "reason": "evidência referencia obrigação desconhecida",
                }
            )
            continue
        try:
            validate_evidence(item)
        except ValueError as exc:
            blockers.append(
                {
                    "code": "invalid_evidence",
                    "evidence_uid": evidence_uid,
                    "norm_uid": norm_uid,
                    "reason": str(exc),
                }
            )
            continue
        evidence_by_uid[norm_uid].append(item)

    return applicability_by_uid, evidence_by_uid, blockers


def _canonical_applicability_decision(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    decision = str(item.get("decision") or "").strip()
    if decision in {"not_applicable", "nao_aplicavel"}:
        return {
            "decision": "nao_aplicavel",
            "decided_by": item.get("decided_by"),
            "decided_at": item.get("decided_at"),
            "rationale": item.get("rationale"),
        }
    return None


def _document_blockers(baseline_v2: dict[str, Any], *, as_of: str) -> tuple[list[dict[str, Any]], int, int]:
    blockers: list[dict[str, Any]] = []
    documents = ((baseline_v2.get("normative_baseline") or {}).get("referenced_documents") or [])
    if not isinstance(documents, list):
        raise ValueError("referenced_documents deve ser lista")
    as_of_date = parse_utc(as_of).date()
    fresh = 0
    stale = 0
    for document in documents:
        if not isinstance(document, dict):
            blockers.append({"code": "invalid_referenced_document", "reason": "documento deve ser objeto"})
            continue
        uid = document.get("uid") or document.get("title") or "unknown"
        hash_state = document.get("hash_state")
        sha256 = str(document.get("content_sha256") or "")
        if hash_state != "captured" or not SHA256_RE.fullmatch(sha256):
            blockers.append(
                {
                    "code": "live_document_hash_not_captured",
                    "document_uid": uid,
                    "reason": "documento vivo precisa de hash normalizado capturado e válido",
                }
            )
        try:
            checked_at = _parse_date(document.get("checked_at"), field=f"{uid}.checked_at")
            cycle_days = int(document.get("check_cycle_days"))
            if cycle_days < 1:
                raise ValueError("check_cycle_days deve ser positivo")
            valid_through = checked_at + timedelta(days=cycle_days)
            if as_of_date > valid_through:
                stale += 1
                blockers.append(
                    {
                        "code": "live_document_check_stale",
                        "document_uid": uid,
                        "checked_at": checked_at.isoformat(),
                        "valid_through": valid_through.isoformat(),
                        "as_of": as_of,
                        "reason": "verificação do documento vivo está fora da janela permitida",
                    }
                )
            else:
                fresh += 1
        except (TypeError, ValueError) as exc:
            stale += 1
            blockers.append(
                {
                    "code": "live_document_freshness_invalid",
                    "document_uid": uid,
                    "reason": str(exc),
                }
            )
    return blockers, fresh, stale


def evaluate_readiness(
    *,
    baseline_v2: dict[str, Any],
    base_obligations: dict[str, Any],
    extended_obligations: dict[str, Any],
    evidence_registry: dict[str, Any],
    policy: dict[str, Any],
    matrix: dict[str, Any],
    reconciliation: dict[str, Any],
    target_stage: str,
    as_of: str,
) -> dict[str, Any]:
    parse_utc(as_of)
    target = normalize_stage(target_stage)
    production_target = target == PRODUCTION_STAGE
    blockers: list[dict[str, Any]] = []

    obligations = _obligations(base_obligations, extended_obligations)
    expected_obligations = int(policy.get("expected_obligations") or 0)
    if expected_obligations and len(obligations) != expected_obligations:
        blockers.append(
            {
                "code": "obligation_count_mismatch",
                "expected": expected_obligations,
                "actual": len(obligations),
                "reason": "universo normativo diferente do contrato do Gate 2",
            }
        )

    known_uids = {str(item.get("uid") or "") for item in obligations}
    if "" in known_uids or len(known_uids) != len(obligations):
        blockers.append(
            {
                "code": "invalid_normative_uids",
                "reason": "obrigações precisam de uid único e não vazio",
            }
        )

    family_decision, family_blockers = _family_applicability_blockers(baseline_v2.get("applicability") or {})
    blockers.extend(family_blockers)

    applicability_by_uid, evidence_by_uid, registry_blockers = _registry_indexes(evidence_registry, known_uids)
    blockers.extend(registry_blockers)

    document_blockers, fresh_documents, stale_documents = _document_blockers(baseline_v2, as_of=as_of)
    blockers.extend(document_blockers)

    status_counts = {
        "nao_avaliado": 0,
        "nao_aplicavel": 0,
        "lacuna": 0,
        "parcial": 0,
        "implementado": 0,
        "evidenciado": 0,
        "nao_derivado_por_aplicabilidade_pendente": 0,
    }
    obligation_results: list[dict[str, Any]] = []
    acceptable = set((policy.get("obligation_readiness") or {}).get("production_acceptable_statuses") or [])

    if family_decision == "applicable" and not family_blockers:
        for obligation in obligations:
            norm_uid = str(obligation.get("uid"))
            applicability_item = applicability_by_uid.get(norm_uid)
            canonical_decision = _canonical_applicability_decision(applicability_item)
            if applicability_item and canonical_decision is None:
                blockers.append(
                    {
                        "code": "invalid_obligation_applicability_decision",
                        "norm_uid": norm_uid,
                        "reason": "decisão por obrigação deve ser not_applicable/nao_aplicavel ou ser omitida",
                    }
                )
            try:
                status = derive_status(
                    obligation=obligation,
                    as_of=as_of,
                    assessment=obligation.get("assessment"),
                    applicability_decision=canonical_decision,
                    evidences=evidence_by_uid.get(norm_uid, []),
                )
            except ValueError as exc:
                blockers.append(
                    {
                        "code": "status_derivation_error",
                        "norm_uid": norm_uid,
                        "reason": str(exc),
                    }
                )
                continue
            status_counts[status] += 1
            result_item = {
                "norm_uid": norm_uid,
                "code": obligation.get("code"),
                "derived_status": status,
            }
            obligation_results.append(result_item)
            if status not in acceptable:
                reason_code = {
                    "nao_avaliado": "obligation_not_evaluated",
                    "lacuna": "implementation_gap",
                    "parcial": "partial_implementation",
                    "implementado": "valid_evidence_missing",
                }.get(status, "obligation_not_production_ready")
                blockers.append(
                    {
                        "code": reason_code,
                        "norm_uid": norm_uid,
                        "obligation_code": obligation.get("code"),
                        "derived_status": status,
                        "reason": "status derivado não atende ao contrato de promoção para produção",
                    }
                )
    elif family_decision == "not_applicable" and not family_blockers:
        status_counts["nao_aplicavel"] = len(obligations)
        obligation_results = [
            {
                "norm_uid": str(item.get("uid")),
                "code": item.get("code"),
                "derived_status": "nao_aplicavel",
                "source": "family_applicability_decision",
            }
            for item in obligations
        ]
    else:
        status_counts["nao_derivado_por_aplicabilidade_pendente"] = len(obligations)

    formal_report = evaluate_formal_gate(matrix, reconciliation, target_stage=PRODUCTION_STAGE)
    if formal_report.get("decision") != "allowed":
        for item in formal_report.get("blockers") or []:
            blockers.append(
                {
                    "code": "institutional_formal_gate_blocked",
                    "control_id": item.get("control_id"),
                    "reason": "; ".join(str(value) for value in (item.get("reasons") or [])),
                }
            )

    production_readiness = "ready" if not blockers else "blocked"
    decision = "blocked" if production_target and blockers else "allowed"
    return {
        "schema_version": "1.0.0",
        "contract": "reqsys-bacen-production-readiness-gate-2",
        "target_stage": target,
        "as_of": as_of,
        "enforced": production_target,
        "decision": decision,
        "production_readiness": production_readiness,
        "would_block_production": bool(blockers),
        "automatic_override_allowed": False,
        "main_branch_blocked_by_institutional_debt": False,
        "family_applicability_decision": family_decision,
        "obligations_total": len(obligations),
        "status_counts": status_counts,
        "referenced_documents": {
            "fresh": fresh_documents,
            "stale_or_invalid": stale_documents,
        },
        "institutional_formal_gate": {
            "decision": formal_report.get("decision"),
            "blockers": len(formal_report.get("blockers") or []),
        },
        "blocker_count": len(blockers),
        "blockers": blockers,
        "obligations": obligation_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-v2", type=Path, required=True)
    parser.add_argument("--base-obligations", type=Path, required=True)
    parser.add_argument("--extended-obligations", type=Path, required=True)
    parser.add_argument("--evidence-registry", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--reconciliation", type=Path, required=True)
    parser.add_argument("--target-stage", required=True)
    parser.add_argument("--as-of", required=True, help="Instante UTC explícito da decisão")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Retorna erro quando o estágio é PRODUCTION e a prontidão está bloqueada.",
    )
    args = parser.parse_args()

    report = evaluate_readiness(
        baseline_v2=load_yaml(args.baseline_v2),
        base_obligations=load_yaml(args.base_obligations),
        extended_obligations=load_yaml(args.extended_obligations),
        evidence_registry=load_yaml(args.evidence_registry),
        policy=load_yaml(args.policy),
        matrix=load_yaml(args.matrix),
        reconciliation=load_yaml(args.reconciliation),
        target_stage=args.target_stage,
        as_of=args.as_of,
    )
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(raw, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")

    if args.enforce and report["target_stage"] == PRODUCTION_STAGE and report["decision"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
