"""Contrato de domínio do ciclo fechado de evidência de CHANGE (RSM-07)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.service_management import ServiceManagementValidationError

_GIT_SHA_RE = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class ChangeValidationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


def _text(value: str, field_name: str, *, max_length: int = 1000) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ServiceManagementValidationError(f"{field_name} deve ser informado")
    if len(normalized) > max_length:
        raise ServiceManagementValidationError(
            f"{field_name} excede {max_length} caracteres"
        )
    return normalized


def _git_sha(value: str, field_name: str) -> str:
    normalized = _text(value, field_name, max_length=64).lower()
    if not _GIT_SHA_RE.fullmatch(normalized):
        raise ServiceManagementValidationError(
            f"{field_name} deve ser SHA Git completo hexadecimal de 40 ou 64 caracteres"
        )
    return normalized


def _digest(value: str, field_name: str) -> str:
    normalized = _text(value, field_name, max_length=64).lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ServiceManagementValidationError(
            f"{field_name} deve ser SHA-256 hexadecimal minúsculo"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class ChangeExecutionEvidence:
    """Evidência runtime imutável e vinculada ao SHA exato do CHANGE."""

    head_sha: str
    deployment_ref: str
    environment: str
    runtime_sha: str
    post_deploy_evidence_uri: str
    post_deploy_evidence_sha256: str
    status: ChangeValidationStatus
    observed_at: datetime
    rollback_ref: str | None = None
    rollback_runtime_sha: str | None = None
    rollback_evidence_uri: str | None = None
    rollback_evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "head_sha", _git_sha(self.head_sha, "head_sha"))
        object.__setattr__(
            self,
            "runtime_sha",
            _git_sha(self.runtime_sha, "runtime_sha"),
        )
        object.__setattr__(
            self,
            "deployment_ref",
            _text(self.deployment_ref, "deployment_ref", max_length=300),
        )
        object.__setattr__(
            self,
            "environment",
            _text(self.environment, "environment", max_length=80),
        )
        object.__setattr__(
            self,
            "post_deploy_evidence_uri",
            _text(
                self.post_deploy_evidence_uri,
                "post_deploy_evidence_uri",
                max_length=1000,
            ),
        )
        object.__setattr__(
            self,
            "post_deploy_evidence_sha256",
            _digest(
                self.post_deploy_evidence_sha256,
                "post_deploy_evidence_sha256",
            ),
        )

        if not isinstance(self.status, ChangeValidationStatus):
            raise ServiceManagementValidationError("status de validação do CHANGE inválido")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ServiceManagementValidationError("observed_at deve possuir timezone")
        if self.runtime_sha != self.head_sha:
            raise ServiceManagementValidationError(
                "runtime SHA divergente do SHA do CHANGE"
            )

        rollback_values = (
            self.rollback_ref,
            self.rollback_runtime_sha,
            self.rollback_evidence_uri,
            self.rollback_evidence_sha256,
        )
        has_any_rollback = any(value is not None for value in rollback_values)
        has_all_rollback = all(value is not None for value in rollback_values)

        if self.status is ChangeValidationStatus.ROLLED_BACK:
            if not has_all_rollback:
                raise ServiceManagementValidationError(
                    "rollback exige referência, runtime SHA e evidência completos"
                )
            rollback_sha = _git_sha(
                str(self.rollback_runtime_sha),
                "rollback_runtime_sha",
            )
            if rollback_sha == self.head_sha:
                raise ServiceManagementValidationError(
                    "rollback_runtime_sha deve divergir do SHA revertido"
                )
            object.__setattr__(self, "rollback_runtime_sha", rollback_sha)
            object.__setattr__(
                self,
                "rollback_ref",
                _text(str(self.rollback_ref), "rollback_ref", max_length=300),
            )
            object.__setattr__(
                self,
                "rollback_evidence_uri",
                _text(
                    str(self.rollback_evidence_uri),
                    "rollback_evidence_uri",
                    max_length=1000,
                ),
            )
            object.__setattr__(
                self,
                "rollback_evidence_sha256",
                _digest(
                    str(self.rollback_evidence_sha256),
                    "rollback_evidence_sha256",
                ),
            )
        elif has_any_rollback:
            raise ServiceManagementValidationError(
                "campos de rollback só são aceitos com status ROLLED_BACK"
            )

    @property
    def allows_close(self) -> bool:
        return self.status in {
            ChangeValidationStatus.PASSED,
            ChangeValidationStatus.ROLLED_BACK,
        }


def assert_change_can_close(evidence: ChangeExecutionEvidence | None) -> None:
    """Bloqueia fechamento sem evidência satisfatória ou rollback comprovado."""
    if evidence is None:
        raise ServiceManagementValidationError(
            "CHANGE não pode ser fechado sem evidência runtime pós-deploy"
        )
    if not evidence.allows_close:
        raise ServiceManagementValidationError(
            "última evidência pós-deploy falhou e rollback não foi comprovado"
        )
