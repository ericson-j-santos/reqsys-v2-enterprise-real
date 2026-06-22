from __future__ import annotations

import hmac
from dataclasses import dataclass

from app.core.secrets import read_secret_from_vault

VERSAO_VERIFICADOR_CEGO = 'cego-v1'
CHAVE_OPERACIONAL_VERIFICADOR = 'REQSYS_COFRE_VERIFICADOR_PEPPER'
_DIGEST = 'sha256'
_CONTEXTO = b'reqsys:cofre:verificador-cego:v1'


class VerificadorCegoIndisponivel(RuntimeError):
    """Indica que o verificador cego nao esta operacional no ambiente."""


@dataclass(frozen=True)
class ResultadoVerificacaoCega:
    key: str
    match: bool
    verifier_version: str = VERSAO_VERIFICADOR_CEGO
    value_exposed: bool = False


def obter_chave_operacional() -> str:
    valor = read_secret_from_vault(CHAVE_OPERACIONAL_VERIFICADOR)
    if not valor or len(valor.encode('utf-8')) < 32:
        raise VerificadorCegoIndisponivel('REQSYS_COFRE_VERIFICADOR_PEPPER ausente ou fraco')
    return valor
