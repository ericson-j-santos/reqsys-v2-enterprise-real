from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import httpx

REQUIRED_CONNECTION_REFERENCES = {
    "shared_excelonlinebusiness",
    "shared_sql",
    "shared_sharepointonline",
}
TIMEOUT = 30.0


class DataverseFlowError(RuntimeError):
    pass


def normalize_dataverse_url(value: str) -> str:
    url = str(value or "").strip().rstrip("/")
    if not url.startswith("https://"):
        raise DataverseFlowError("dataverse_url_invalida")
    return url


def workflow_url(dataverse_url: str, flow_id: str) -> str:
    flow_id = str(flow_id or "").strip()
    if not flow_id:
        raise DataverseFlowError("flow_id_ausente")
    return f"{normalize_dataverse_url(dataverse_url)}/api/data/v9.2/workflows({flow_id})"


def parse_clientdata(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(str(raw or ""))
    except json.JSONDecodeError as exc:
        raise DataverseFlowError("clientdata_invalido") from exc
    if not isinstance(payload, dict):
        raise DataverseFlowError("clientdata_invalido")
    props = payload.get("properties")
    if not isinstance(props, dict):
        raise DataverseFlowError("clientdata_properties_ausente")
    refs = props.get("connectionReferences")
    if not isinstance(refs, dict):
        raise DataverseFlowError("connection_references_ausentes")
    missing = sorted(REQUIRED_CONNECTION_REFERENCES - set(refs))
    if missing:
        raise DataverseFlowError("connection_references_incompletas:" + ",".join(missing))
    return payload


def merge_definition(raw: str, definition: dict[str, Any]) -> str:
    if not isinstance(definition, dict) or not definition.get("actions") or not definition.get("triggers"):
        raise DataverseFlowError("definition_invalida")
    payload = deepcopy(parse_clientdata(raw))
    payload["properties"]["definition"] = definition
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _headers(token: str) -> dict[str, str]:
    if not str(token or "").strip():
        raise DataverseFlowError("dataverse_token_ausente")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
    }


def get_flow(client: httpx.Client, dataverse_url: str, flow_id: str, token: str) -> dict[str, Any]:
    response = client.get(
        workflow_url(dataverse_url, flow_id),
        params={"$select": "workflowid,name,statecode,statuscode,category,type,clientdata"},
        headers=_headers(token),
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if int(payload.get("category", -1)) != 5 or int(payload.get("type", -1)) != 1:
        raise DataverseFlowError("workflow_nao_e_modern_flow_definition")
    parse_clientdata(str(payload.get("clientdata") or ""))
    return payload


def patch_flow(
    client: httpx.Client,
    dataverse_url: str,
    flow_id: str,
    token: str,
    body: dict[str, Any],
) -> None:
    headers = _headers(token)
    headers["If-Match"] = "*"
    response = client.patch(
        workflow_url(dataverse_url, flow_id),
        headers=headers,
        json=body,
        timeout=TIMEOUT,
    )
    if response.status_code != 204:
        raise DataverseFlowError(f"dataverse_flow_patch_http_{response.status_code}")


def install_definition(
    client: httpx.Client,
    dataverse_url: str,
    flow_id: str,
    token: str,
    definition: dict[str, Any],
) -> str:
    current = get_flow(client, dataverse_url, flow_id, token)
    if int(current.get("statecode", -1)) != 0:
        raise DataverseFlowError("flow_deve_estar_desligado_antes_da_atualizacao")
    original = str(current.get("clientdata") or "")
    patch_flow(
        client,
        dataverse_url,
        flow_id,
        token,
        {"clientdata": merge_definition(original, definition)},
    )
    return original


def set_state(
    client: httpx.Client,
    dataverse_url: str,
    flow_id: str,
    token: str,
    statecode: int,
) -> None:
    if statecode not in {0, 1}:
        raise DataverseFlowError("statecode_nao_permitido")
    patch_flow(client, dataverse_url, flow_id, token, {"statecode": statecode})
    observed = get_flow(client, dataverse_url, flow_id, token)
    if int(observed.get("statecode", -1)) != statecode:
        raise DataverseFlowError(f"statecode_nao_confirmado:{statecode}")


def restore_clientdata(
    client: httpx.Client,
    dataverse_url: str,
    flow_id: str,
    token: str,
    original_clientdata: str,
) -> None:
    current = get_flow(client, dataverse_url, flow_id, token)
    if int(current.get("statecode", -1)) != 0:
        set_state(client, dataverse_url, flow_id, token, 0)
    parse_clientdata(original_clientdata)
    patch_flow(
        client,
        dataverse_url,
        flow_id,
        token,
        {"clientdata": original_clientdata},
    )
