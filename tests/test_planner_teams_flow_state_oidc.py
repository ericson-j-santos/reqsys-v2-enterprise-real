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
