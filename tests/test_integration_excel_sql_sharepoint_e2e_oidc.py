from scripts.integration_excel_sql_sharepoint_e2e_oidc import item_version


def test_item_version_prefere_etag():
    assert item_version({"eTag": '"abc"', "lastModifiedDateTime": "2026-01-01"}) == '"abc"'


def test_item_version_usa_data_como_fallback():
    assert item_version({"lastModifiedDateTime": "2026-01-01T00:00:00Z"}) == "2026-01-01T00:00:00Z"
