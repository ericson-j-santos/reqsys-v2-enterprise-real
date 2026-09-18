import json

import pytest

from scripts.planner_teams_flow_state_oidc import (
    FlowStateError,
    connection_keys,
    select_flow,
)


def row(name="ReqSys - Notificar Teams (Tarefa criada no Planner)", statecode=0):
    return {
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
                    }
                }
            }
        ),
    }


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
