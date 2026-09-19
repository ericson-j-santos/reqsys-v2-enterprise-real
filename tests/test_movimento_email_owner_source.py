from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path("scripts/movimento_email_owner_source.py")
SPEC = importlib.util.spec_from_file_location("movimento_email_owner_source", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def payload() -> dict:
    ref = "2026-09-19"
    return {
        "data_referencia": ref,
        "datasets": {
            "fechamento_diario": [
                {"indicador": "QTD", "valor": "1", "observacao": "real", "data_referencia": ref}
            ],
            "pendencias_cadastro": [
                {
                    "protocolo": "P-1",
                    "cliente": "CLIENTE",
                    "cpf": "00000000000",
                    "pendencia": "DOCUMENTO",
                    "dias_em_aberto": 1,
                    "responsavel": "ERICSON",
                    "data_referencia": ref,
                }
            ],
            "pendencias_historicas": [
                {
                    "periodo_referencia": "2026-09",
                    "pendencia": "DOCUMENTO",
                    "quantidade": 1,
                    "percentual": "100.00",
                    "data_referencia": ref,
                }
            ],
            "pendencias_observacao": [
                {
                    "protocolo": "P-1",
                    "tipo_inconsistencia": "VALIDACAO",
                    "descricao": "registro",
                    "etapa": "OWNER",
                    "data_referencia": ref,
                }
            ],
        },
    }


def test_payload_contract_accepts_exact_four_datasets() -> None:
    ref, datasets = module._normalize_payload(payload())
    assert ref.isoformat() == "2026-09-19"
    assert set(datasets) == set(module.DATASETS)
    assert len(datasets["pendencias_cadastro"]) == 1


def test_payload_contract_rejects_missing_dataset() -> None:
    data = payload()
    del data["datasets"]["pendencias_observacao"]
    with pytest.raises(RuntimeError, match="dataset_contract_mismatch"):
        module._normalize_payload(data)


def test_payload_contract_rejects_extra_or_missing_columns() -> None:
    data = payload()
    del data["datasets"]["fechamento_diario"][0]["observacao"]
    with pytest.raises(RuntimeError, match="columns_invalid"):
        module._normalize_payload(data)


def test_payload_contract_rejects_reference_drift() -> None:
    data = payload()
    data["datasets"]["pendencias_historicas"][0]["data_referencia"] = "2026-09-18"
    with pytest.raises(RuntimeError, match="reference_mismatch"):
        module._normalize_payload(data)


def test_owner_source_is_local_and_dev_only() -> None:
    assert module._safe_local_server("localhost") == "localhost"
    assert module._safe_dev_database("ReqSysMovimentoOwnerDev") == "ReqSysMovimentoOwnerDev"
    with pytest.raises(RuntimeError, match="local_sql"):
        module._safe_local_server("remote-sql")
    with pytest.raises(RuntimeError, match="Dev_database"):
        module._safe_dev_database("ReqSysMovimentoProd")


def test_hash_is_idempotent_and_sensitive() -> None:
    a = module._sha({"x": 1, "y": 2})
    b = module._sha({"y": 2, "x": 1})
    c = module._sha({"x": 1, "y": 3})
    assert a == b
    assert c != a


def test_owner_source_has_no_embedded_business_seed() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "CLIENTE DEMO" not in text
    assert "EQUIV-" not in text
    assert '"synthetic": true' not in text.casefold()


def test_schema_contains_owner_contract_without_login_or_user_creation() -> None:
    schema = Path(
        "backend/app/services/movimento_email/sql/owner/V1__owner_source_schema.sql"
    ).read_text(encoding="utf-8")
    upper = schema.upper()
    for name in module.DATASETS:
        assert f"OWNER_MOVIMENTO.{name.upper()}" in upper
        assert f"VW_PROSPECCAO_MOVIMENTO_{name.upper()}" in upper
    assert "CREATE LOGIN" not in upper
    assert "CREATE USER" not in upper
