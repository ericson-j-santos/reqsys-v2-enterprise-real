import copy
import json

import pytest

import scripts.planner_teams_flow_state_oidc as mod
from scripts.planner_teams_flow_state_oidc import (
    FlowStateError,
    PLANNER_TASK_URL,
    card_contract,
    connection_keys,
    desired_card,
    patch_clientdata,
    reconcile_card_clientdata,
    select_flow,
)


def legacy_card():
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": "Nova tarefa criada no Planner",
            },
            {
                "type": "TextBlock",
                "wrap": True,
                "text": "@{triggerBody()?['title']}",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Plano", "value": "@{parameters('PLANNER_PLAN_ID')}"},
                    {
                        "title": "Percentual",
                        "value": "@{string(triggerBody()?['percentComplete'])}%",
                    },
                    {
                        "title": "Vencimento",
                        "value": "@{coalesce(triggerBody()?['dueDateTime'], 'sem prazo')}",
                    },
                ],
            },
        ],
    }


def row(
    name="ReqSys - Notificar Teams (Tarefa criada no Planner)",
    statecode=0,
    *,
    message_body=None,
):
    card = legacy_card() if message_body is None else message_body
    if isinstance(card, dict):
        card = json.dumps(card, ensure_ascii=False)
    return {
        "@odata.etag": 'W/"123456"',
        "workflowid": "00000000-0000-0000-0000-000000000001",
        "name": name,
        "statecode": statecode,
        "statuscode": 1,
        "category": 5,
        "type": 1,
        "clientdata": json.dumps(
            {
                "properties": {
                    "connectionReferences": {
                        "shared_planner": {"connectionName": "planner"},
                        "shared_teams": {"connectionName": "teams"},
                    },
                    "definition": {
                        "actions": {
                            "Ignorar_tarefas_de_teste_automatizado": {
                                "type": "If",
                                "actions": {
                                    "Notificar_Teams": {
                                        "type": "OpenApiConnection",
                                        "inputs": {
                                            "host": {
                                                "apiId": "/providers/Microsoft.PowerApps/apis/shared_teams",
                                                "operationId": "PostCardToConversation",
                                                "connectionName": "shared_teams",
                                            },
                                            "parameters": {
                                                "poster": "Flow bot",
                                                "location": "Channel",
                                                "body/recipient/groupId": "@parameters('TEAMS_TEAM_ID')",
                                                "body/recipient/channelId": "@parameters('TEAMS_CHANNEL_ID')",
                                                "body/messageBody": card,
                                            },
                                        },
                                    }
                                },
                                "else": {"actions": {}},
                            }
                        }
                    },
                }
            },
            ensure_ascii=False,
        ),
    }


def _notify(clientdata):
    return clientdata["properties"]["definition"]["actions"][
        "Ignorar_tarefas_de_teste_automatizado"
    ]["actions"]["Notificar_Teams"]


def test_select_flow_exige_modern_flow_unico():
    item = row()
    assert select_flow([item], item["name"]) == item


def test_select_flow_rejeita_duplicidade():
    item = row()
    with pytest.raises(FlowStateError, match="flow_ambiguo"):
        select_flow([item, dict(item, workflowid="2")], item["name"])


def test_connection_keys_exige_planner_e_teams():
    assert connection_keys(row()) == ["shared_planner", "shared_teams"]
    broken = row()
    payload = json.loads(broken["clientdata"])
    del payload["properties"]["connectionReferences"]["shared_teams"]
    broken["clientdata"] = json.dumps(payload)
    with pytest.raises(FlowStateError, match="shared_teams"):
        connection_keys(broken)


def test_reconcile_card_remove_id_do_plano_e_adiciona_acao_direta():
    source = row()
    before = json.loads(source["clientdata"])
    before_notify = copy.deepcopy(_notify(before))

    raw_after, changed, contract_before, contract_after = reconcile_card_clientdata(
        source,
        source["name"],
    )

    assert changed is True
    assert contract_before == {
        "title": "Nova tarefa criada no Planner",
        "facts": ["Percentual", "Plano", "Vencimento"],
        "has_plan_fact": True,
        "has_progress_fact": False,
        "has_open_planner": False,
    }
    assert contract_after == {
        "title": "Nova tarefa no Planner",
        "facts": ["Progresso", "Vencimento"],
        "has_plan_fact": False,
        "has_progress_fact": True,
        "has_open_planner": True,
    }

    after = json.loads(raw_after)
    after_notify = _notify(after)
    before_parameters = before_notify["inputs"]["parameters"]
    after_parameters = after_notify["inputs"]["parameters"]
    for key in (
        "poster",
        "location",
        "body/recipient/groupId",
        "body/recipient/channelId",
    ):
        assert after_parameters[key] == before_parameters[key]
    assert after_notify["inputs"]["host"] == before_notify["inputs"]["host"]
    assert after_parameters["body/messageBody"] != before_parameters["body/messageBody"]


def test_reconcile_card_e_idempotente_quando_runtime_ja_esta_correto():
    source = row(message_body=desired_card("ReqSys - Notificar Teams (Tarefa criada no Planner)"))

    raw_after, changed, _before, after = reconcile_card_clientdata(
        source,
        source["name"],
    )

    assert changed is False
    assert raw_after == source["clientdata"]
    assert after["facts"] == ["Progresso", "Vencimento"]
    assert after["has_open_planner"] is True


def test_card_concluido_mantem_titulo_e_link_da_tarefa():
    name = "ReqSys - Notificar Teams (Tarefa concluída no Planner)"
    source = row(name=name, message_body=desired_card(name))

    contract = card_contract(json.loads(source["clientdata"]))
    card = desired_card(name)

    assert contract["title"] == "Tarefa concluída no Planner"
    assert card["actions"] == [
        {
            "type": "Action.OpenUrl",
            "title": "Abrir no Planner",
            "url": PLANNER_TASK_URL,
        }
    ]


def test_reconcile_falha_fechado_quando_message_body_nao_e_json():
    source = row(message_body="@outputs('Compose_Message')")

    with pytest.raises(FlowStateError, match="flow_card_message_body_invalido"):
        reconcile_card_clientdata(source, source["name"])


def test_reconcile_falha_fechado_quando_operacao_teams_diverge():
    source = row()
    payload = json.loads(source["clientdata"])
    _notify(payload)["inputs"]["host"]["operationId"] = "PostMessageToConversation"
    source["clientdata"] = json.dumps(payload)

    with pytest.raises(FlowStateError, match="flow_notificar_teams_operacao_invalida"):
        reconcile_card_clientdata(source, source["name"])


def test_patch_clientdata_usa_etag_exato(monkeypatch):
    source = row()
    calls = []

    def fake_request(method, url, token, body=None, *, if_match=None):
        calls.append(
            {
                "method": method,
                "url": url,
                "token": token,
                "body": body,
                "if_match": if_match,
            }
        )
        return 204, {}

    monkeypatch.setattr(mod, "request_json", fake_request)

    patch_clientdata("https://org.crm.dynamics.com", "token", source, '{"x":1}')

    assert calls == [
        {
            "method": "PATCH",
            "url": (
                "https://org.crm.dynamics.com/api/data/v9.2/workflows"
                "(00000000-0000-0000-0000-000000000001)"
            ),
            "token": "token",
            "body": {"clientdata": '{"x":1}'},
            "if_match": 'W/"123456"',
        }
    ]


def test_patch_clientdata_falha_fechado_sem_etag():
    source = row()
    source.pop("@odata.etag")

    with pytest.raises(FlowStateError, match="flow_etag_ausente"):
        patch_clientdata("https://org.crm.dynamics.com", "token", source, '{"x":1}')


class FakeDataverse:
    """Dataverse minimo que recusa PATCH de clientdata em flow ativado."""

    def __init__(self, source, *, reject_card_patch=False):
        self.row = copy.deepcopy(source)
        self.reject_card_patch = reject_card_patch
        self.calls = []

    def request(self, method, url, token, body=None, *, if_match=None):
        self.calls.append((method, body))
        if method == "GET":
            return 200, copy.deepcopy(self.row)
        if method != "PATCH":
            raise AssertionError(f"metodo inesperado: {method}")

        if "clientdata" in body:
            if int(self.row["statecode"]) == 1:
                return 400, {
                    "error": {
                        "code": "0x80040203",
                        "message": "Invalid Argument\nworkflow ativado",
                    }
                }
            if self.reject_card_patch:
                return 400, {"error": {"code": "0x80040203", "message": "recusado"}}
            self.row["clientdata"] = body["clientdata"]
            return 204, {}

        self.row["statecode"] = body["statecode"]
        self.row["statuscode"] = body["statuscode"]
        return 204, {}

    def state_patches(self):
        return [
            (body["statecode"], body["statuscode"])
            for method, body in self.calls
            if method == "PATCH" and "statecode" in body
        ]


def _install(monkeypatch, fake):
    monkeypatch.setattr(mod, "request_json", fake.request)
    monkeypatch.setattr(mod.time, "sleep", lambda _seconds: None)


def test_reconcile_flow_card_desativa_flow_ativo_antes_do_patch(monkeypatch):
    fake = FakeDataverse(row(statecode=1))
    _install(monkeypatch, fake)

    after, evidence = mod.reconcile_flow_card(
        "https://org.crm.dynamics.com",
        "token",
        copy.deepcopy(fake.row),
        "ReqSys - Notificar Teams (Tarefa criada no Planner)",
    )

    assert evidence["card_reconciled"] is True
    assert evidence["flow_deactivated_for_patch"] is True
    # desativa (0,1) antes do patch e devolve o flow ao estado ativado (1,2).
    assert fake.state_patches() == [(0, 1), (1, 2)]
    assert int(after["statecode"]) == 1
    assert int(after["statuscode"]) == 2
    assert evidence["card_after"]["has_plan_fact"] is False
    assert evidence["card_after"]["has_open_planner"] is True


def test_reconcile_flow_card_nao_desativa_flow_ja_inativo(monkeypatch):
    fake = FakeDataverse(row(statecode=0))
    _install(monkeypatch, fake)

    _after, evidence = mod.reconcile_flow_card(
        "https://org.crm.dynamics.com",
        "token",
        copy.deepcopy(fake.row),
        "ReqSys - Notificar Teams (Tarefa criada no Planner)",
    )

    assert evidence["flow_deactivated_for_patch"] is False
    assert fake.state_patches() == []


def test_reconcile_flow_card_reativa_flow_quando_patch_falha(monkeypatch):
    fake = FakeDataverse(row(statecode=1), reject_card_patch=True)
    _install(monkeypatch, fake)

    with pytest.raises(FlowStateError, match="dataverse_card_patch_http_400"):
        mod.reconcile_flow_card(
            "https://org.crm.dynamics.com",
            "token",
            copy.deepcopy(fake.row),
            "ReqSys - Notificar Teams (Tarefa criada no Planner)",
        )

    # falhar nunca pode deixar o flow DEV desativado.
    assert fake.state_patches() == [(0, 1), (1, 2)]
    assert int(fake.row["statecode"]) == 1
    assert int(fake.row["statuscode"]) == 2


def test_reconcile_flow_card_sem_mudanca_nao_toca_no_estado(monkeypatch):
    source = row(statecode=1, message_body=mod.desired_card(
        "ReqSys - Notificar Teams (Tarefa criada no Planner)"
    ))
    fake = FakeDataverse(source)
    _install(monkeypatch, fake)

    _after, evidence = mod.reconcile_flow_card(
        "https://org.crm.dynamics.com",
        "token",
        copy.deepcopy(source),
        "ReqSys - Notificar Teams (Tarefa criada no Planner)",
    )

    assert evidence["card_reconciled"] is False
    assert evidence["flow_deactivated_for_patch"] is False
    assert fake.calls == []


def test_patch_clientdata_propaga_mensagem_do_dataverse(monkeypatch):
    fake = FakeDataverse(row(statecode=1))
    _install(monkeypatch, fake)

    with pytest.raises(
        FlowStateError,
        match=r"dataverse_card_patch_http_400:0x80040203:Invalid Argument workflow ativado",
    ):
        patch_clientdata(
            "https://org.crm.dynamics.com",
            "token",
            row(statecode=1),
            '{"x":1}',
        )


def test_error_detail_sem_mensagem_mantem_apenas_o_codigo():
    assert mod.error_detail({"error": {"code": "0x80040203"}}) == "0x80040203"
    assert mod.error_detail({}) == ""
