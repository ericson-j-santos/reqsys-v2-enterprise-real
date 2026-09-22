"""Governança de identidades de aplicação e rotação de credenciais.

A seleção de uma identidade é fail-closed: ambiente, finalidade e classificação
precisam corresponder exatamente ao perfil cadastrado. O módulo não armazena
segredos; mantém apenas referências para o cofre/provider de secrets.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable


class IdentityGovernanceError(RuntimeError):
    """Erro de política de identidade/credencial."""


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class ApplicationIdentityProfile:
    name: str
    environment: str
    purpose: str
    data_classification: DataClassification
    tenant_id: str
    client_id: str
    current_secret_ref: str
    next_secret_ref: str
    rotated_at: datetime
    max_age_days: int = 90

    @property
    def rotation_due_at(self) -> datetime:
        return self.rotated_at + timedelta(days=self.max_age_days)

    def requires_rotation(self, *, now: datetime | None = None, warning_days: int = 14) -> bool:
        instant = now or datetime.now(timezone.utc)
        return instant >= self.rotation_due_at - timedelta(days=warning_days)

    def is_expired(self, *, now: datetime | None = None) -> bool:
        instant = now or datetime.now(timezone.utc)
        return instant >= self.rotation_due_at


class ApplicationIdentityRegistry:
    """Registro imutável de identidades autorizadas por contexto."""

    def __init__(self, profiles: Iterable[ApplicationIdentityProfile]):
        self._profiles = tuple(profiles)
        self._validate_registry()

    @classmethod
    def from_json_file(cls, path: str | Path) -> "ApplicationIdentityRegistry":
        source = Path(path)
        if not source.exists():
            raise IdentityGovernanceError(f"Arquivo de governança não encontrado: {source}")

        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise IdentityGovernanceError("O arquivo de governança deve conter uma lista JSON.")

        profiles: list[ApplicationIdentityProfile] = []
        for item in payload:
            profiles.append(
                ApplicationIdentityProfile(
                    name=_required(item, "name"),
                    environment=_normalize_environment(_required(item, "environment")),
                    purpose=_required(item, "purpose").strip().lower(),
                    data_classification=DataClassification(_required(item, "data_classification").strip().lower()),
                    tenant_id=_required(item, "tenant_id"),
                    client_id=_required(item, "client_id"),
                    current_secret_ref=_required(item, "current_secret_ref"),
                    next_secret_ref=_required(item, "next_secret_ref"),
                    rotated_at=_parse_utc(_required(item, "rotated_at")),
                    max_age_days=int(item.get("max_age_days", 90)),
                )
            )
        return cls(profiles)

    @classmethod
    def from_environment(cls) -> "ApplicationIdentityRegistry":
        path = os.getenv("REQSYS_IDENTITY_GOVERNANCE_FILE", "").strip()
        if not path:
            raise IdentityGovernanceError(
                "REQSYS_IDENTITY_GOVERNANCE_FILE não configurado; seleção de identidade bloqueada."
            )
        return cls.from_json_file(path)

    def resolve(
        self,
        *,
        environment: str,
        purpose: str,
        data_classification: DataClassification | str,
        now: datetime | None = None,
    ) -> ApplicationIdentityProfile:
        env = _normalize_environment(environment)
        normalized_purpose = purpose.strip().lower()
        classification = (
            data_classification
            if isinstance(data_classification, DataClassification)
            else DataClassification(data_classification.strip().lower())
        )

        matches = [
            profile
            for profile in self._profiles
            if profile.environment == env
            and profile.purpose == normalized_purpose
            and profile.data_classification == classification
        ]

        if len(matches) != 1:
            raise IdentityGovernanceError(
                "Identidade não resolvida de forma unívoca para "
                f"environment={env}, purpose={normalized_purpose}, classification={classification.value}."
            )

        profile = matches[0]
        if profile.is_expired(now=now):
            raise IdentityGovernanceError(
                f"Credencial do perfil {profile.name!r} expirou em {profile.rotation_due_at.isoformat()}; "
                "execução bloqueada até a rotação."
            )
        return profile

    def rotation_report(self, *, now: datetime | None = None, warning_days: int = 14) -> list[dict[str, object]]:
        instant = now or datetime.now(timezone.utc)
        return [
            {
                "name": profile.name,
                "environment": profile.environment,
                "purpose": profile.purpose,
                "data_classification": profile.data_classification.value,
                "rotation_due_at": profile.rotation_due_at.isoformat(),
                "expired": profile.is_expired(now=instant),
                "rotation_required": profile.requires_rotation(now=instant, warning_days=warning_days),
                "current_secret_ref": profile.current_secret_ref,
                "next_secret_ref": profile.next_secret_ref,
            }
            for profile in self._profiles
        ]

    def _validate_registry(self) -> None:
        if not self._profiles:
            raise IdentityGovernanceError("Nenhum perfil de identidade cadastrado.")

        keys: set[tuple[str, str, DataClassification]] = set()
        for profile in self._profiles:
            if profile.max_age_days <= 0 or profile.max_age_days > 90:
                raise IdentityGovernanceError(
                    f"Perfil {profile.name!r}: max_age_days deve estar entre 1 e 90 dias."
                )
            if profile.current_secret_ref == profile.next_secret_ref:
                raise IdentityGovernanceError(
                    f"Perfil {profile.name!r}: current_secret_ref e next_secret_ref devem ser distintos."
                )
            if _looks_like_secret(profile.current_secret_ref) or _looks_like_secret(profile.next_secret_ref):
                raise IdentityGovernanceError(
                    f"Perfil {profile.name!r}: informe referências de segredo, nunca o segredo em claro."
                )

            key = (profile.environment, profile.purpose, profile.data_classification)
            if key in keys:
                raise IdentityGovernanceError(
                    f"Perfil duplicado para environment={key[0]}, purpose={key[1]}, classification={key[2].value}."
                )
            keys.add(key)

        protected = [
            profile
            for profile in self._profiles
            if profile.data_classification in {DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED}
        ]
        client_context: dict[str, tuple[str, str, DataClassification]] = {}
        for profile in protected:
            context = (profile.environment, profile.purpose, profile.data_classification)
            previous = client_context.get(profile.client_id)
            if previous is not None and previous != context:
                raise IdentityGovernanceError(
                    f"client_id {profile.client_id!r} reutilizado entre contextos protegidos; "
                    "use App Registration dedicada."
                )
            client_context[profile.client_id] = context


def _required(item: object, field: str) -> str:
    if not isinstance(item, dict):
        raise IdentityGovernanceError("Cada perfil deve ser um objeto JSON.")
    value = str(item.get(field, "")).strip()
    if not value:
        raise IdentityGovernanceError(f"Campo obrigatório ausente: {field}")
    return value


def _normalize_environment(value: str) -> str:
    normalized = value.strip().lower()
    aliases = {"dev": "development", "stg": "staging", "hml": "staging", "prd": "production", "prod": "production"}
    return aliases.get(normalized, normalized)


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IdentityGovernanceError(f"rotated_at inválido: {value!r}") from exc
    if parsed.tzinfo is None:
        raise IdentityGovernanceError("rotated_at deve conter timezone explícito.")
    return parsed.astimezone(timezone.utc)


def _looks_like_secret(value: str) -> bool:
    normalized = value.lower()
    allowed_prefixes = ("vault://", "keyvault://", "github-secret://", "env://")
    return not normalized.startswith(allowed_prefixes)
