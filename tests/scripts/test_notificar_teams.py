import json
from io import BytesIO
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.notificar_teams import enviar_mensagem, main


class _FakeResponse:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_enviar_mensagem_retorna_data_em_sucesso(monkeypatch):
    def fake_urlopen(request, timeout):
        assert request.full_url == "https://reqsys-api.fly.dev/v1/teams-gateway/messages"
        body = json.loads(request.data.decode("utf-8"))
        assert body["modo"] == "auto"
        assert body["texto"] == "ola"
        return _FakeResponse({"success": True, "data": {"entregue": True, "canal_usado": "flow_bot"}})

    monkeypatch.setattr("scripts.notificar_teams.urlopen", fake_urlopen)

    resultado = enviar_mensagem(
        base_url="https://reqsys-api.fly.dev",
        texto="ola",
        titulo="Titulo",
        modo="auto",
        destino_tipo="chat",
        destino_id="user@example.com",
        autor="reqsys-ci",
        permitir_fallback=True,
        dry_run=False,
        timeout=10.0,
    )

    assert resultado["entregue"] is True
    assert resultado["canal_usado"] == "flow_bot"


def test_policy_404_usa_destino_explicito_no_endpoint_legado(monkeypatch):
    chamadas = []

    def fake_urlopen(request, timeout):
        chamadas.append(request.full_url)
        body = json.loads(request.data.decode("utf-8"))
        if request.full_url.endswith("/recipient-policies/hitl-approvers/messages"):
            assert body["delivery_mode"] == "all"
            raise HTTPError(
                request.full_url,
                404,
                "Not Found",
                {},
                BytesIO(b'{"detail":"Not Found"}'),
            )
        assert request.full_url.endswith("/v1/teams-gateway/messages")
        assert "delivery_mode" not in body
        assert body["destino_id"] == "user@example.com"
        return _FakeResponse(
            {
                "success": True,
                "data": {
                    "entregue": True,
                    "canal_usado": "flow_bot",
                    "provider_response": {"message_id": "msg-1"},
                },
            }
        )

    monkeypatch.setattr("scripts.notificar_teams.urlopen", fake_urlopen)

    resultado = enviar_mensagem(
        base_url="https://reqsys-api.fly.dev",
        texto="ola",
        titulo="Titulo",
        modo="auto",
        destino_tipo="auto",
        destino_id="user@example.com",
        autor="reqsys-hitl",
        permitir_fallback=True,
        dry_run=False,
        timeout=10.0,
        recipient_policy="hitl-approvers",
        delivery_mode="all",
    )

    assert chamadas == [
        "https://reqsys-api.fly.dev/v1/teams-gateway/recipient-policies/hitl-approvers/messages",
        "https://reqsys-api.fly.dev/v1/teams-gateway/messages",
    ]
    assert resultado["entregue"] is True
    assert resultado["fallback_usado"] is True
    assert resultado["provider_response"]["resolution"] == "legacy_endpoint_fallback"
    assert resultado["provider_response"]["policy_endpoint_error"] == "http_404"


def test_policy_404_sem_destino_preserva_erro(monkeypatch):
    chamadas = []

    def fake_urlopen(request, timeout):
        chamadas.append(request.full_url)
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            BytesIO(b'{"detail":"Not Found"}'),
        )

    monkeypatch.setattr("scripts.notificar_teams.urlopen", fake_urlopen)

    resultado = enviar_mensagem(
        base_url="https://reqsys-api.fly.dev",
        texto="ola",
        titulo="Titulo",
        modo="auto",
        destino_tipo="auto",
        destino_id=None,
        autor="reqsys-hitl",
        permitir_fallback=True,
        dry_run=False,
        timeout=10.0,
        recipient_policy="hitl-approvers",
        delivery_mode="all",
    )

    assert len(chamadas) == 1
    assert resultado["entregue"] is False
    assert resultado["erro"] == "http_404"


def test_enviar_mensagem_trata_erro_de_rede(monkeypatch):
    def fake_urlopen(request, timeout):
        raise URLError("falhou")

    monkeypatch.setattr("scripts.notificar_teams.urlopen", fake_urlopen)

    resultado = enviar_mensagem(
        base_url="https://reqsys-api.fly.dev",
        texto="ola",
        titulo="Titulo",
        modo="auto",
        destino_tipo="chat",
        destino_id="user@example.com",
        autor="reqsys-ci",
        permitir_fallback=True,
        dry_run=False,
        timeout=10.0,
    )

    assert resultado["entregue"] is False
    assert resultado["erro"] == "network_error"


def test_main_nao_falha_por_padrao_quando_nao_entregue(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout):
        raise URLError("falhou")

    monkeypatch.setattr("scripts.notificar_teams.urlopen", fake_urlopen)
    saida = tmp_path / "resultado.json"

    sys.argv = [
        "notificar_teams.py",
        "--texto", "ola",
        "--destino-id", "user@example.com",
        "--output", str(saida),
    ]
    codigo = main()

    assert codigo == 0
    dados = json.loads(saida.read_text(encoding="utf-8"))
    assert dados["entregue"] is False


def test_main_falha_com_strict_quando_nao_entregue(monkeypatch, tmp_path):
    def fake_urlopen(request, timeout):
        raise URLError("falhou")

    monkeypatch.setattr("scripts.notificar_teams.urlopen", fake_urlopen)
    saida = tmp_path / "resultado.json"

    sys.argv = [
        "notificar_teams.py",
        "--texto", "ola",
        "--destino-id", "user@example.com",
        "--output", str(saida),
        "--strict",
    ]
    codigo = main()

    assert codigo == 1
