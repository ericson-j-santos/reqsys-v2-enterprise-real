#!/usr/bin/env python3
"""Read-only probe for GitHub Copilot cloud-agent repository metadata.

The probe intentionally excludes Agents credential endpoints. It reads only:
- repository Copilot cloud-agent configuration;
- one named Agents variable required by the Ollama MCP profile.

Evidence is sanitized before writing: the variable value and MCP configuration
body are never persisted.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_VERSION = "2026-03-10"
VARIABLE_NAME = "COPILOT_MCP_OLLAMA_URL"
CLOUD_CONFIG_PATH = "copilot/cloud-agent/configuration"
VARIABLE_PATH = f"agents/variables/{VARIABLE_NAME}"


def _request_json(repository: str, path: str, bearer: str) -> tuple[int, dict[str, Any]]:
    url = f"https://api.github.com/repos/{repository}/{path}"
    request = Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
        },
    )
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed GitHub API host.
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return int(response.status), payload if isinstance(payload, dict) else {}
    except HTTPError as exc:
        # Do not persist the API response body. Status is enough for capability diagnosis.
        return int(exc.code), {}
    except URLError:
        return 0, {}


def sanitize_cloud_configuration(payload: dict[str, Any]) -> dict[str, Any]:
    enabled_tools = payload.get("enabled_tools")
    tools = enabled_tools if isinstance(enabled_tools, dict) else {}
    bool_fields = (
        "require_actions_workflow_approval",
        "is_firewall_enabled",
        "is_firewall_recommended_allowlist_enabled",
        "is_automations_enabled",
        "require_write_access_for_automation_triggers",
    )
    result: dict[str, Any] = {
        "top_level_keys": sorted(str(key) for key in payload),
        "enabled_tools": sorted(str(key) for key, value in tools.items() if value is True),
        "disabled_tools": sorted(str(key) for key, value in tools.items() if value is False),
        "mcp_configuration_present": payload.get("mcp_configuration") is not None,
    }
    for key in bool_fields:
        value = payload.get(key)
        result[key] = value if isinstance(value, bool) else None
    return result


def sanitize_variable(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("value")
    return {
        "name": payload.get("name"),
        "exists": payload.get("name") == VARIABLE_NAME,
        "value_present": isinstance(value, str) and bool(value.strip()),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
    }


def build_evidence(repository: str, bearer: str, correlation_id: str, auth_source: str) -> dict[str, Any]:
    config_status, config_payload = _request_json(repository, CLOUD_CONFIG_PATH, bearer)
    variable_status, variable_payload = _request_json(
        repository,
        f"agents/variables/{quote(VARIABLE_NAME, safe='')}",
        bearer,
    )
    config = sanitize_cloud_configuration(config_payload) if config_status == 200 else {}
    variable = sanitize_variable(variable_payload) if variable_status == 200 else {}

    passed = (
        config_status == 200
        and variable_status == 200
        and variable.get("exists") is True
        and variable.get("value_present") is True
    )
    return {
        "schema_version": "1.0.0",
        "contract": "copilot-cloud-agent-metadata-probe",
        "repository": repository,
        "correlation_id": correlation_id,
        "api_version": API_VERSION,
        "result": "COPILOT_AGENT_METADATA_PROBE_PASSED" if passed else "COPILOT_AGENT_METADATA_ACCESS_BLOCKED",
        "cloud_agent_configuration": {
            "http_status": config_status,
            "metadata": config,
        },
        "ollama_mcp_variable": {
            "http_status": variable_status,
            "metadata": variable,
            "value_persisted": False,
        },
        "credential_endpoint_called": False,
        "mcp_configuration_body_persisted": False,
        "mutation_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args()

    bearer = os.environ.get("GITHUB_TOKEN", "").strip()
    if not bearer:
        raise SystemExit("GITHUB_TOKEN ausente")

    evidence = build_evidence(args.repository, bearer, args.correlation_id, args.auth_source)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": evidence["result"],
        "auth_source": evidence["auth_source"],\n        "cloud_config_status": evidence["cloud_agent_configuration"]["http_status"],
        "variable_status": evidence["ollama_mcp_variable"]["http_status"],
        "credential_endpoint_called": False,
    }, ensure_ascii=False))
    return 0 if evidence["result"] == "COPILOT_AGENT_METADATA_PROBE_PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
