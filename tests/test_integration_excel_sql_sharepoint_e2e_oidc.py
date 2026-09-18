import httpx
import pytest

import scripts.integration_excel_sql_sharepoint_e2e_oidc as module
from scripts.integration_excel_sql_sharepoint_e2e_oidc import (
    OidcE2EError,
    cleanup_stale_fixture_items,
    item_version,
)


def test_item_version_prefere_etag():
    assert item_version({"eTag": '"abc"', "lastModifiedDateTime": "2026-01-01"}) == '"abc"'


def test_item_version_usa_data_como_fallback():
    assert item_version({"lastModifiedDateTime": "2026-01-01T00:00:00Z"}) == "2026-01-01T00:00:00Z"


def test_cleanup_remove_somente_fixture_com_correlation_e2e(monkeypatch):
    calls = {"list": 0, "deleted": []}
    stale = {
        "id": "123",
        "fields": {
            "ChaveIntegracao": "990000000000001",
            "CorrelationId": "excel-sql-sharepoint-oidc-old-1",
        },
    }

    def fake_list_items(*args, **kwargs):
        calls["list"] += 1
        return [stale] if calls["list"] == 1 else []

    def fake_delete(*args, **kwargs):
        calls["deleted"].append(args[-1])

    monkeypatch.setattr(module, "list_items", fake_list_items)
    monkeypatch.setattr(module, "delete_sharepoint_item", fake_delete)

    removed = cleanup_stale_fixture_items(
        httpx.Client(),
        "token",
        "site",
        "list",
        "990000000000001",
    )

    assert removed == 1
    assert calls["deleted"] == ["123"]


def test_cleanup_falha_fechado_para_item_sem_correlation_e2e(monkeypatch):
    stale = {
        "id": "123",
        "fields": {
            "ChaveIntegracao": "990000000000001",
            "CorrelationId": "business-correlation",
        },
    }
    monkeypatch.setattr(module, "list_items", lambda *args, **kwargs: [stale])
    monkeypatch.setattr(
        module,
        "delete_sharepoint_item",
        lambda *args, **kwargs: pytest.fail("nao deveria excluir dado nao-E2E"),
    )

    with pytest.raises(OidcE2EError, match="baseline_sharepoint_non_e2e_data_detectado"):
        cleanup_stale_fixture_items(
            httpx.Client(),
            "token",
            "site",
            "list",
            "990000000000001",
        )
