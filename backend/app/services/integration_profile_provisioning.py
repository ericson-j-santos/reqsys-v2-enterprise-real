from __future__ import annotations

import json
import uuid
from typing import Any, Iterator

import httpx

from app.services.integration_profile_generator import PROFILE, validate_profile

FLOW_MANAGEMENT_BASE = "https://api.flow.microsoft.com/providers/Microsoft.ProcessSimple"
ALLOWED_API_IDS = {
    "/providers/Microsoft.PowerApps/apis/shared_excelonlinebusiness",
    "/providers/Microsoft.PowerApps/apis/shared_sql",
    "/providers/Microsoft.PowerApps/apis/shared_sharepointonline",
}
REQUIRED_CONNECTIONS = {
    "shared_excelonlinebusiness",
    "shared_sql",
    "shared_sharepointonline",
}


def _segmento_id_seguro(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{label} obrigatório")
    parts = normalized.split("-")
    if any(not part or not part.isalnum() for part in parts):
        raise ValueError(f"{label} inválido")
    return "-".join(parts)


def _walk_actions(actions: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for name, action in actions.items():
        yield name, action
        nested = action.get("actions")
        if isinstance(nested, dict):
            yield from _walk_actions(nested)
        else_actions = action.get("else", {}).get("actions")
        if isinstance(else_actions, dict):
            yield from _walk_actions(else_actions)


def validar_definicao(definition: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(definition, dict):
        return ["definicao_ausente"]
    if not definition.get("triggers"):
        errors.append("gatilho_ausente")
    actions = definition.get("actions")
    if not isinstance(actions, dict) or not actions:
        errors.append("acoes_ausentes")
        return errors
    observed_connections: set[str] = set()
    for name, action in _walk_actions(actions):
        if action.get("type") != "OpenApiConnection":
            continue
        host = action.get("inputs", {}).get("host", {})
        api_id = host.get("apiId")
        connection_name = host.get("connectionName")
        if api_id not in ALLOWED_API_IDS:
            errors.append(f"conector_nao_permitido:{name}")
        if connection_name:
            observed_connections.add(connection_name)
    missing = sorted(REQUIRED_CONNECTIONS - observed_connections)
    errors.extend(f"conexao_nao_usada:{name}" for name in missing)
    raw = json.dumps(definition, ensure_ascii=False)
    if "CorrelationId" not in raw and "correlation_id" not in raw:
        errors.append("correlation_id_ausente")
    return errors


def montar_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    target = str(payload.get("target_environment") or "dev").strip().lower()
    if target not in {"dev", "development"}:
        raise ValueError("O perfil excel_sql_sharepoint_sync está restrito a DEV neste incremento")

    profile = payload.get("profile_contract")
    if not isinstance(profile, dict):
        raise ValueError("profile_contract é obrigatório")
    validate_profile(profile)

    definition = payload.get("flow_definition")
    errors = validar_definicao(definition)
    if errors:
        raise ValueError(f"Definição Power Automate inválida: {errors}")

    connections = payload.get("connections") or {}
    missing_connections = sorted(name for name in REQUIRED_CONNECTIONS if not connections.get(name))
    if missing_connections:
        raise ValueError(f"Conexões obrigatórias ausentes: {missing_connections}")

    correlation_id = payload.get("correlation_id") or str(uuid.uuid4())
    display_name = str(payload.get("display_name") or "ReqSys - Excel SQL SharePoint DEV").strip()
    if not display_name:
        raise ValueError("display_name obrigatório")

    return {
        "schema_version": "1.0.0",
        "profile": PROFILE,
        "correlation_id": correlation_id,
        "target": {
            "environment_id": _segmento_id_seguro(payload.get("environment_id"), "Ambiente"),
            "target_environment": "dev",
        },
        "flow": {
            "display_name": display_name,
            "state": "Stopped",
            "definition": definition,
        },
        "connections": {name: connections[name] for name in sorted(REQUIRED_CONNECTIONS)},
        "controls": {
            "dev_only": True,
            "allowed_connectors_only": True,
            "idempotent_by_display_name": True,
            "starts_stopped": True,
        },
    }


async def _buscar_flow_existente(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    display_name: str,
) -> str | None:
    response = await client.get(base_url, headers=headers, params={"api-version": "2016-11-01"})
    if response.status_code != 200:
        return None
    for item in response.json().get("value", []):
        if item.get("properties", {}).get("displayName") == display_name:
            return item.get("name")
    return None


async def despachar(payload: dict[str, Any], *, user_token: str | None = None) -> dict[str, Any]:
    bundle = montar_bundle(payload)
    if not payload.get("confirmar"):
        return {
            "dispatched": False,
            "status": "validado_sem_implantar",
            "correlation_id": bundle["correlation_id"],
            "bundle": bundle,
        }
    if not user_token:
        return {
            "dispatched": False,
            "status": "pending_configuration",
            "correlation_id": bundle["correlation_id"],
            "erro": "Token delegado do Power Automate ausente.",
        }

    environment_id = bundle["target"]["environment_id"]
    base_url = f"{FLOW_MANAGEMENT_BASE}/environments/{environment_id}/flows"
    headers = {"Authorization": f"Bearer {user_token}"}
    references = {
        name: {
            "connectionName": connection_id,
            "id": f"/providers/Microsoft.PowerApps/apis/{name}",
        }
        for name, connection_id in bundle["connections"].items()
    }
    body = {
        "properties": {
            "displayName": bundle["flow"]["display_name"],
            "definition": bundle["flow"]["definition"],
            "connectionReferences": references,
            "state": "Stopped",
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        flow_id = await _buscar_flow_existente(client, base_url, headers, bundle["flow"]["display_name"])
        if flow_id:
            response = await client.patch(
                f"{base_url}/{flow_id}",
                headers=headers,
                params={"api-version": "2016-11-01"},
                json=body,
            )
            operation = "updated"
        else:
            response = await client.post(
                base_url,
                headers=headers,
                params={"api-version": "2016-11-01"},
                json=body,
            )
            operation = "created"

    if response.status_code not in (200, 201):
        return {
            "dispatched": False,
            "status": "erro_provisionamento",
            "status_code": response.status_code,
            "erro": response.text[:500],
            "correlation_id": bundle["correlation_id"],
        }

    data = response.json()
    resolved_flow_id = data.get("name") or flow_id
    return {
        "dispatched": True,
        "status": "implantado_parado",
        "operation": operation,
        "correlation_id": bundle["correlation_id"],
        "flow_id": resolved_flow_id,
        "flow_url": (
            f"https://make.powerautomate.com/environments/{environment_id}/flows/"
            f"{resolved_flow_id}/details"
        ),
    }
