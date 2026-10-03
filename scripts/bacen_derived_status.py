#!/usr/bin/env python3
"""Status regulatório derivado e modelo temporal de evidências BACEN.

Status nunca é entrada. A função é pura para um mesmo conjunto de entradas e `as_of`.
Validade e retenção são derivadas de `event_at`, nunca de `collected_at`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

ALLOWED_STATUS = (
    "nao_avaliado",
    "nao_aplicavel",
    "lacuna",
    "parcial",
    "implementado",
    "evidenciado",
)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp deve estar em UTC")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class EvidencePolicy:
    validity_days: int | None = None
    retention_days: int | None = None

    def __post_init__(self) -> None:
        for field in ("validity_days", "retention_days"):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise ValueError(f"{field} não pode ser negativo")


def derive_temporal_fields(event_at: str, policy: EvidencePolicy) -> dict[str, str | None]:
    event = parse_utc(event_at)
    valid_until = event + timedelta(days=policy.validity_days) if policy.validity_days is not None else None
    retention_until = event + timedelta(days=policy.retention_days) if policy.retention_days is not None else None
    return {
        "valid_until": valid_until.isoformat().replace("+00:00", "Z") if valid_until else None,
        "retention_until": retention_until.isoformat().replace("+00:00", "Z") if retention_until else None,
    }


def validate_evidence(evidence: dict[str, Any]) -> None:
    forbidden = {"status"} & set(evidence)
    if forbidden:
        raise ValueError("evidência não pode declarar status")
    required = {"uid", "norm_uid", "event_at", "collected_at", "sha256", "source"}
    missing = sorted(required - set(evidence))
    if missing:
        raise ValueError(f"campos obrigatórios ausentes: {', '.join(missing)}")
    event_at = parse_utc(str(evidence["event_at"]))
    collected_at = parse_utc(str(evidence["collected_at"]))
    if collected_at < event_at:
        raise ValueError("collected_at não pode anteceder event_at")
    sha256 = str(evidence["sha256"])
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256.casefold()):
        raise ValueError("sha256 inválido")
    if evidence.get("valid_until") is not None and parse_utc(str(evidence["valid_until"])) < event_at:
        raise ValueError("valid_until não pode anteceder event_at")
    if evidence.get("retention_until") is not None and parse_utc(str(evidence["retention_until"])) < event_at:
        raise ValueError("retention_until não pode anteceder event_at")


def evidence_is_valid(evidence: dict[str, Any], as_of: str) -> bool:
    validate_evidence(evidence)
    instant = parse_utc(as_of)
    event_at = parse_utc(str(evidence["event_at"]))
    if event_at > instant:
        return False
    valid_until = evidence.get("valid_until")
    return valid_until is None or instant <= parse_utc(str(valid_until))


def evidence_must_be_retained(evidence: dict[str, Any], as_of: str) -> bool:
    validate_evidence(evidence)
    retention_until = evidence.get("retention_until")
    if retention_until is None:
        return False
    return parse_utc(as_of) <= parse_utc(str(retention_until))


def validate_applicability_decision(decision: dict[str, Any] | None) -> bool:
    if not decision or decision.get("decision") != "nao_aplicavel":
        return False
    required = ("decided_by", "decided_at", "rationale")
    if not all(decision.get(field) for field in required):
        raise ValueError("nao_aplicavel exige decided_by, decided_at e rationale")
    parse_utc(str(decision["decided_at"]))
    return True


def derive_status(
    *,
    obligation: dict[str, Any],
    as_of: str,
    assessment: dict[str, Any] | None = None,
    applicability_decision: dict[str, Any] | None = None,
    evidences: Iterable[dict[str, Any]] = (),
) -> str:
    """Deriva o status sem depender do relógio do sistema."""
    parse_utc(as_of)
    if "status" in obligation:
        raise ValueError("obrigação não pode declarar status manual")
    if assessment and "status" in assessment:
        raise ValueError("assessment não pode declarar status manual")
    if validate_applicability_decision(applicability_decision):
        return "nao_aplicavel"
    if assessment is None:
        return "nao_avaliado"

    evaluated = bool(assessment.get("evaluated", False))
    if not evaluated:
        return "nao_avaliado"
    implementation = assessment.get("implementation")
    if implementation in (None, "none", "nao_implementado"):
        return "lacuna"
    if implementation in ("partial", "parcial"):
        return "parcial"
    if implementation not in ("complete", "completo", "implementado"):
        raise ValueError(f"implementation inválido: {implementation}")

    valid_evidence = False
    for evidence in evidences:
        if evidence.get("norm_uid") != obligation.get("uid"):
            continue
        if evidence_is_valid(evidence, as_of):
            valid_evidence = True
            break
    return "evidenciado" if valid_evidence else "implementado"
