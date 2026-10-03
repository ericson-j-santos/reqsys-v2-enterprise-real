from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from app.core.secrets import get_secret

_PAPEIS_PERMITIDOS = {'admin', 'analista', 'auditor', 'gestor'}
_DEFAULT_ENTRA_ROLE_MAP = {
    'ReqSys.Admin': 'admin',
    'ReqSys.Analyst': 'analista',
    'ReqSys.Auditor': 'auditor',
    'ReqSys.Manager': 'gestor',
}


@dataclass(frozen=True)
class PapelResolvido:
    papel: str
    origem: str


def _normalizar_identidade(email: str) -> str:
    return (email or '').strip().lower()


def _papel_seguro(valor: object) -> str | None:
    papel = str(valor or '').strip().lower()
    return papel if papel in _PAPEIS_PERMITIDOS else None


def _carregar_json_objeto(nome: str, default: dict[str, str] | None = None) -> dict[str, str]:
    raw = get_secret(nome, '') or ''
    if not raw.strip():
        return dict(default or {})
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def _bindings_identidade() -> dict[str, str]:
    bindings = _carregar_json_objeto('REQSYS_ROLE_BINDINGS')
    resultado: dict[str, str] = {}
    for identidade, papel_raw in bindings.items():
        papel = _papel_seguro(papel_raw)
        if papel:
            resultado[_normalizar_identidade(identidade)] = papel
    return resultado


def _mapa_roles_entra() -> dict[str, str]:
    mapa = _carregar_json_objeto('REQSYS_ENTRA_ROLE_MAP', _DEFAULT_ENTRA_ROLE_MAP)
    resultado: dict[str, str] = {}
    for role, papel_raw in mapa.items():
        papel = _papel_seguro(papel_raw)
        if papel:
            resultado[str(role).strip()] = papel
    return resultado


def resolver_papel(email: str, entra_roles: Iterable[str] | None = None) -> PapelResolvido:
    """Resolve identidade -> papel sem elevar privilégio por heurística de e-mail.

    Precedência:
    1. binding explícito governado por identidade exata (`REQSYS_ROLE_BINDINGS`);
    2. App Role do Microsoft Entra ID (`REQSYS_ENTRA_ROLE_MAP`);
    3. papel padrão não privilegiado (`REQSYS_DEFAULT_ROLE`, default `analista`).

    Configuração ausente ou inválida nunca resulta em `admin` por fallback.
    """
    identidade = _normalizar_identidade(email)
    binding = _bindings_identidade().get(identidade)
    if binding:
        return PapelResolvido(binding, 'configured_identity')

    mapa_roles = _mapa_roles_entra()
    for role in entra_roles or ():
        papel = mapa_roles.get(str(role).strip())
        if papel:
            return PapelResolvido(papel, 'entra_app_role')

    papel_default = _papel_seguro(get_secret('REQSYS_DEFAULT_ROLE', 'analista'))
    if papel_default == 'admin' or papel_default is None:
        papel_default = 'analista'
    return PapelResolvido(papel_default, 'default_fail_closed')
