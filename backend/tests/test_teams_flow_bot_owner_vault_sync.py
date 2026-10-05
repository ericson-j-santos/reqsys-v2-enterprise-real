from unittest.mock import patch

from app.services import teams_gateway


class Owner:
    def __init__(self, webhook_url="https://old.invalid"):
        self.id = 7
        self.owner_email = "owner@example.com"
        self.webhook_url = webhook_url
        self.observacao = ""


class DB:
    def __init__(self):
        self.commits = 0
    def commit(self):
        self.commits += 1
    def refresh(self, _item):
        return None


def test_sync_owner_from_vault_updates_without_exposing_secret():
    secret = "https://example.invalid/flow?sig=super-secret"
    owner = Owner()
    db = DB()
    with patch.object(teams_gateway, "get_secret", return_value=secret), patch.object(
        teams_gateway, "listar_flow_bot_owners", return_value=[owner]
    ):
        result = teams_gateway.sincronizar_flow_bot_owner_do_cofre(db)
    assert result["changed"] is True
    assert result["configured"] is True
    assert result["secret_value_exposed"] is False
    assert "super-secret" not in str(result)
    assert owner.webhook_url == secret
    assert db.commits == 1


def test_sync_owner_from_vault_is_idempotent():
    secret = "https://example.invalid/flow?sig=stable"
    owner = Owner(secret)
    db = DB()
    with patch.object(teams_gateway, "get_secret", return_value=secret), patch.object(
        teams_gateway, "listar_flow_bot_owners", return_value=[owner]
    ):
        result = teams_gateway.sincronizar_flow_bot_owner_do_cofre(db)
    assert result["changed"] is False
    assert db.commits == 0


def test_sync_owner_from_vault_fails_closed_without_secret():
    db = DB()
    with patch.object(teams_gateway, "get_secret", return_value=""):
        try:
            teams_gateway.sincronizar_flow_bot_owner_do_cofre(db)
        except ValueError as exc:
            assert str(exc) == "teams_flow_bot_webhook_url_absent"
        else:
            raise AssertionError("expected fail-closed")
