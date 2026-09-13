from __future__ import annotations

import json

import pytest

from scripts.normalize_msal_storage_state import StorageStateError, normalize_bundle, normalize_file


def test_normaliza_storage_misto_sem_expor_valores(tmp_path):
    secret = "refresh-token-nao-vazar"
    payload = {
        "cookies": [],
        "sessionStorage": [
            {"name": "refresh", "value": json.dumps({"credentialType": "RefreshToken", "secret": secret, "clientId": "client"})},
            {"name": "boolean", "value": "true"},
            {"name": "array", "value": "[]"},
            {"name": "texto-nao-json", "value": "valor-normal"},
            False,
        ],
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    kept, removed = normalize_file(path)
    result = json.loads(path.read_text(encoding="utf-8"))

    assert kept == 2
    assert removed == 3
    assert [item["name"] for item in result["sessionStorage"]] == ["refresh", "texto-nao-json"]
    assert secret in result["sessionStorage"][0]["value"]


def test_envelope_deve_ser_objeto():
    with pytest.raises(StorageStateError, match="envelope_invalido"):
        normalize_bundle([])


def test_session_storage_deve_ser_lista():
    with pytest.raises(StorageStateError, match="session_storage_invalido"):
        normalize_bundle({"sessionStorage": {}})


def test_campos_fora_de_session_storage_sao_preservados():
    payload = {"cookies": [{"name": "cookie"}], "origins": [], "sessionStorage": []}
    normalized, removed = normalize_bundle(payload)

    assert removed == 0
    assert normalized["cookies"] == payload["cookies"]
    assert normalized["origins"] == []
