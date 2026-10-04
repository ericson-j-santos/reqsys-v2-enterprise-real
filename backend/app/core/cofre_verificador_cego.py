from __future__ import annotations

import hmac
from dataclasses import dataclass

from app.core.secrets import read_secret_from_vault

VERSAO_VERIFICADOR_CEGO = 'cego-v1'
CHAVE_OPERACIONAL_VERIFICADOR = 'REQSYS_COFRE_VERIFICADOR_PEPPER'
_DIGEST = 'sha256'
_CONTEXTO = b'reqsys:cofre:verificador-cego:v1'


class VerificadorCegoIndisponivel(RuntimeError):
    """Indica ausência de material criptográfico suficiente para a verificação."""


@dataclass(frozen=True)
class ResultadoVerificacaoCega:
    key: str
    match: bool
    verifier_version: str = VERSAO_VERIFICADOR_CEGO
    value_exposed: bool = False


def obter_chave_operacional() -> str:
    valor = read_secret_from_vault(CHAVE_OPERACIONAL_VERIFICADOR)
    if not valor or len(valor.encode('utf-8')) < 32:
        raise VerificadorCegoIndisponivel('chave operacional do verificador ausente ou fraca')
    return valor


def _derivar_chave(valor_operacional: str, key: str) -> bytes:
    return hmac.digest(
        valor_operacional.encode('utf-8'),
        _CONTEXTO + b':' + key.encode('utf-8'),
        _DIGEST,
    )


def _marcador(valor_operacional: str, key: str, value: str) -> bytes:
    return hmac.digest(_derivar_chave(valor_operacional, key), value.encode('utf-8'), _DIGEST)


def verificar_valor_cego(key: str, valor_armazenado: str, valor_candidato: str) -> ResultadoVerificacaoCega:
    """Compara marcadores HMAC em tempo constante sem retornar segredo, digest ou fingerprint."""
    valor_operacional = obter_chave_operacional()
    return ResultadoVerificacaoCega(
        key=key,
        match=hmac.compare_digest(
            _marcador(valor_operacional, key, valor_armazenado),
            _marcador(valor_operacional, key, valor_candidato),
        ),
    )
