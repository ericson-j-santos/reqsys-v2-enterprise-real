import logging
from functools import lru_cache

import jwt
from jwt import PyJWKClient

logger = logging.getLogger('reqsys.azure_auth')

_JWKS_URL = 'https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys'
_V1_ISSUER = 'https://sts.windows.net/{tenant_id}/'
_V2_ISSUER = 'https://login.microsoftonline.com/{tenant_id}/v2.0'


@lru_cache(maxsize=1)
def _get_jwks_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(_JWKS_URL.format(tenant_id=tenant_id), cache_keys=True)


def validar_token_azure(id_token: str, tenant_id: str, client_id: str) -> dict:
    """Valida ID token emitido pelo Azure AD e retorna os claims."""
    try:
        client = _get_jwks_client(tenant_id)
        signing_key = client.get_signing_key_from_jwt(id_token)
    except Exception as e:
        raise ValueError(f'Token inválido ou não reconhecido pelo Azure AD: {e}') from e

    issuers = [
        _V1_ISSUER.format(tenant_id=tenant_id),
        _V2_ISSUER.format(tenant_id=tenant_id),
    ]

    last_err: Exception | None = None
    for issuer in issuers:
        try:
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=['RS256'],
                audience=client_id,
                issuer=issuer,
                options={'verify_nbf': True},
            )
            logger.info('azure_auth: token valido sub=%s', claims.get('sub'))
            return claims
        except jwt.exceptions.InvalidIssuerError:
            last_err = Exception('issuer mismatch')
            continue
        except Exception as e:
            raise ValueError(f'Token Azure AD inválido: {e}') from e

    raise ValueError(f'Token Azure AD: issuer não reconhecido ({last_err})')


def extrair_usuario(claims: dict) -> dict:
    """Extrai email e nome dos claims do ID token."""
    email = (
        claims.get('upn')
        or claims.get('preferred_username')
        or claims.get('email')
        or claims.get('unique_name', '')
    )
    nome = claims.get('name', email.split('@')[0].capitalize() if email else 'Usuário')
    return {'email': email, 'nome': nome}
