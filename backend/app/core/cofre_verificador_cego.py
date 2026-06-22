from __future__ import annotations

from app.core.secrets import read_secret_from_vault


CHAVE_OPERACIONAL_VERIFICADOR = 'REQSYS_COFRE_VERIFICADOR_PEPPER'


def obter_chave_operacional() -> str | None:
    return read_secret_from_vault(CHAVE_OPERACIONAL_VERIFICADOR)
