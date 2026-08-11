"""Autenticacao S2S para rotas admin via token de servico escopado.

Mesma logica do VaultToken (ADR-041: hash SHA-256, revogavel, auditavel),
generalizada para qualquer rota `require_admin` — usada quando o chamador e
uma automacao (ex.: GitHub Actions) e nao um usuario humano logado via JWT.
"""

import hashlib
import json
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db import get_db
from app.models.service_token import ServiceToken

HEADER_NAME = 'X-Service-Token'

_bearer_optional = HTTPBearer(auto_error=False)


class ServiceAuthContext:
    """Identidade resolvida por JWT admin ou por token de servico escopado."""

    def __init__(self, ator: str, via_token: bool):
        self.ator = ator
        self.via_token = via_token


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _resolver_token(db: Session, token_bruto: str) -> ServiceToken | None:
    registro = (
        db.query(ServiceToken)
        .filter(ServiceToken.token_hash == hash_token(token_bruto), ServiceToken.revoked_at.is_(None))
        .first()
    )
    if registro is None:
        return None
    if registro.expires_at is not None and registro.expires_at <= datetime.now(timezone.utc):
        return None
    return registro


def _tem_escopo(registro: ServiceToken, escopo: str) -> bool:
    escopos = json.loads(registro.scopes)
    return '*' in escopos or escopo in escopos


def require_admin_or_service_token(escopo: str):
    """Dependency factory: aceita JWT com papel=admin OU X-Service-Token com o escopo pedido."""

    def dependency(
        x_service_token: str | None = Header(default=None, alias=HEADER_NAME),
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
        db: Session = Depends(get_db),
    ) -> ServiceAuthContext:
        if x_service_token:
            registro = _resolver_token(db, x_service_token)
            if registro is None:
                raise HTTPException(status_code=401, detail='Token de serviço inválido, expirado ou revogado')
            if not _tem_escopo(registro, escopo):
                raise HTTPException(status_code=403, detail=f'Token de serviço sem escopo para "{escopo}"')
            registro.last_used_at = datetime.now(timezone.utc)
            db.add(registro)
            db.commit()
            return ServiceAuthContext(ator=f'service-token:{registro.label}', via_token=True)

        if credentials:
            user = get_current_user(credentials=credentials)
            if user.get('papel') != 'admin':
                raise HTTPException(status_code=403, detail='Acesso restrito a administradores')
            return ServiceAuthContext(ator=user.get('sub', 'admin'), via_token=False)

        raise HTTPException(status_code=401, detail='Nenhuma credencial fornecida (JWT admin ou X-Service-Token)')

    return dependency
