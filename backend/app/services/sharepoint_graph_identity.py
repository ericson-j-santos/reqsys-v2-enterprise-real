from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.core.config import settings
from app.core.identity_governance import (
    ApplicationIdentityRegistry,
    DataClassification,
    IdentityGovernanceError,
)
from app.core.secrets import read_secret_from_remote_vault, read_secret_from_vault

_GRAPH_TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
_SHAREPOINT_PURPOSE = 'sharepoint-package-catalog-read'
_SHAREPOINT_DATA_CLASSIFICATION = DataClassification.CONFIDENTIAL


@dataclass(frozen=True)
class SharePointGraphIdentity:
    profile_name: str
    environment: str
    tenant_id: str
    client_id: str
    client_secret: str
    rotation_due_at: datetime
    rotation_required: bool

    def evidence(self) -> dict[str, object]:
        return {
            'profile_name': self.profile_name,
            'environment': self.environment,
            'purpose': _SHAREPOINT_PURPOSE,
            'data_classification': _SHAREPOINT_DATA_CLASSIFICATION.value,
            'client_id_suffix': self.client_id[-8:] if self.client_id else '',
            'rotation_due_at': self.rotation_due_at.isoformat(),
            'rotation_required': self.rotation_required,
        }


def _resolve_secret_reference(reference: str) -> str:
    value = reference.strip()
    if '://' not in value:
        raise IdentityGovernanceError('Referência de segredo inválida para SharePoint Graph.')

    provider, key = value.split('://', 1)
    provider = provider.strip().lower()
    key = key.strip()
    if not key:
        raise IdentityGovernanceError('Referência de segredo do SharePoint Graph sem chave.')

    secret: str | None
    if provider in {'env', 'github-secret'}:
        secret = os.getenv(key)
    elif provider == 'vault':
        secret = read_secret_from_vault(key)
        if secret in (None, ''):
            secret = read_secret_from_remote_vault(key)
    elif provider == 'keyvault':
        raise IdentityGovernanceError(
            'Referência keyvault:// ainda não possui provider configurado no backend; execução bloqueada.'
        )
    else:
        raise IdentityGovernanceError(f'Provider de segredo não suportado para SharePoint Graph: {provider}.')

    if secret in (None, ''):
        raise IdentityGovernanceError(
            f'Segredo atual do SharePoint Graph não resolvido pelo provider {provider!r}; execução bloqueada.'
        )
    return secret


def resolve_sharepoint_graph_identity(*, now: datetime | None = None) -> SharePointGraphIdentity:
    registry = ApplicationIdentityRegistry.from_environment()
    profile = registry.resolve(
        environment=settings.app_environment,
        purpose=_SHAREPOINT_PURPOSE,
        data_classification=_SHAREPOINT_DATA_CLASSIFICATION,
        now=now,
    )
    secret = _resolve_secret_reference(profile.current_secret_ref)
    return SharePointGraphIdentity(
        profile_name=profile.name,
        environment=profile.environment,
        tenant_id=profile.tenant_id,
        client_id=profile.client_id,
        client_secret=secret,
        rotation_due_at=profile.rotation_due_at,
        rotation_required=profile.requires_rotation(now=now),
    )


def sharepoint_graph_identity_status(*, now: datetime | None = None) -> dict[str, object]:
    try:
        identity = resolve_sharepoint_graph_identity(now=now)
    except (IdentityGovernanceError, ValueError) as exc:
        return {
            'configured': False,
            'purpose': _SHAREPOINT_PURPOSE,
            'data_classification': _SHAREPOINT_DATA_CLASSIFICATION.value,
            'error': str(exc),
        }
    return {'configured': True, **identity.evidence()}


async def acquire_sharepoint_graph_token(*, now: datetime | None = None) -> tuple[str, SharePointGraphIdentity]:
    identity = resolve_sharepoint_graph_identity(now=now)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            _GRAPH_TOKEN_URL.format(tenant=identity.tenant_id),
            data={
                'grant_type': 'client_credentials',
                'client_id': identity.client_id,
                'client_secret': identity.client_secret,
                'scope': 'https://graph.microsoft.com/.default',
            },
        )
        response.raise_for_status()
        token = response.json().get('access_token')
    if not token:
        raise IdentityGovernanceError('Microsoft Entra não retornou access_token para o perfil SharePoint Graph.')
    return str(token), identity
