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


def _derivar_chave_interna(valor_operacional: str, key: str) -> bytes:
    return hmac.digest(
        valor_operacional.encode('utf-8'),
        _CONTEXTO + b':inner:' + key.encode('utf-8'),
        _DIGEST,
    )


def _derivar_chave_externa(valor_operacional: str, key: str) -> bytes:
    chave_interna = _derivar_chave_interna(valor_operacional, key)
    return hmac.digest(
        valor_operacional.encode('utf-8'),
        _CONTEXTO + b':outer:' + key.encode('utf-8') + b':' + chave_interna,
        _DIGEST,
    )


def _calcular_marcador_cego(valor_operacional: str, key: str, value: str) -> bytes:
    chave_externa = _derivar_chave_externa(valor_operacional, key)
    return hmac.digest(chave_externa, value.encode('utf-8'), _DIGEST)


def verificar_valor_cego(key: str, valor_armazenado: str, valor_candidato: str) -> ResultadoVerificacaoCega:
    """Compara valor armazenado e candidato sem retornar texto claro, digest ou fingerprint."""
    valor_operacional = obter_chave_operacional()
    marcador_armazenado = _calcular_marcador_cego(valor_operacional, key, valor_armazenado)
    marcador_candidato = _calcular_marcador_cego(valor_operacional, key, valor_candidato)
    return ResultadoVerificacaoCega(
        key=key,
        match=hmac.compare_digest(marcador_armazenado, marcador_candidato),
    )
