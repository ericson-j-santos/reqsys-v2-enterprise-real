from __future__ import annotations

from scripts.resolve_integration_e2e_sql_dsn import resolve_sql_dsn


def test_prefere_dsn_dev_explicito_quando_valido() -> None:
    env = {"INTEGRATION_E2E_SQL_DSN": "dsn-e2e"}

    selected, evidence = resolve_sql_dsn(
        env,
        validator=lambda dsn, _: (dsn == "dsn-e2e", None),
    )

    assert selected is not None
    assert selected.source == "github:INTEGRATION_E2E_SQL_DSN"
    assert evidence["status"] == "resolved"
    assert evidence["environment"] == "dev"
    assert evidence["secret_exposed"] is False


def test_nao_reutiliza_dsn_de_outra_integracao() -> None:
    env = {"MOVIMENTO_EMAIL_SOURCE_DSN": "dsn-movimento"}

    selected, evidence = resolve_sql_dsn(
        env,
        validator=lambda *_: (True, None),
    )

    assert selected is None
    assert evidence["status"] == "blocked"
    assert evidence["attempts"] == []


def test_rejeita_dsn_dev_que_nao_contem_procedure() -> None:
    env = {"INTEGRATION_E2E_SQL_DSN": "dsn-incorreto"}

    selected, evidence = resolve_sql_dsn(
        env,
        validator=lambda *_: (False, "stored_procedure_ausente"),
    )

    assert selected is None
    assert evidence["status"] == "blocked"
    assert evidence["blocked_code"] == "sql_dsn_dev_validado_ausente"
    assert evidence["attempts"][0]["reason"] == "stored_procedure_ausente"


def test_consulta_chave_dev_homonima_no_cofre_sem_expor_valor() -> None:
    env = {"COFRE_API_URL": "https://cofre.example", "VAULT_API_TOKEN": "token"}
    keys: list[str] = []

    def vault_getter(_base: str, _token: str, key: str) -> str | None:
        keys.append(key)
        if key == "INTEGRATION_E2E_SQL_DSN":
            return "dsn-vault"
        return None

    selected, evidence = resolve_sql_dsn(
        env,
        validator=lambda dsn, _: (dsn == "dsn-vault", None),
        vault_getter=vault_getter,
    )

    assert selected is not None
    assert selected.source == "cofre:INTEGRATION_E2E_SQL_DSN"
    assert keys == ["INTEGRATION_E2E_SQL_DSN"]
    assert "dsn-vault" not in str(evidence)
    assert evidence["secret_exposed"] is False


def test_falha_fechada_sem_candidato_dev() -> None:
    selected, evidence = resolve_sql_dsn({}, validator=lambda *_: (True, None))

    assert selected is None
    assert evidence["status"] == "blocked"
    assert evidence["blocked_code"] == "sql_dsn_dev_validado_ausente"
    assert evidence["attempts"] == []
