from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx

TOKEN_TIMEOUT = 20.0
API_TIMEOUT = 30.0
POWER_PLATFORM_ENVIRONMENTS_URL = (
    "https://api.powerplatform.com/environmentmanagement/environments"
    "?api-version=2024-10-01"
)
GRAPH_GROUPS_URL = "https://graph.microsoft.com/v1.0/groups?$top=1&$select=id,displayName"


def _required_env() -> tuple[str, str, str]:
    values = {
        "AZURE_TENANT_ID": os.getenv("AZURE_TENANT_ID", "").strip(),
        "AZURE_CLIENT_ID": os.getenv("AZURE_CLIENT_ID", "").strip(),
        "AZURE_CLIENT_SECRET": os.getenv("AZURE_CLIENT_SECRET", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("Variáveis Microsoft ausentes: " + ", ".join(missing))
    return values["AZURE_TENANT_ID"], values["AZURE_CLIENT_ID"], values["AZURE_CLIENT_SECRET"]


def _token(client: httpx.Client, tenant_id: str, client_id: str, client_secret: str, scope: str) -> str:
    response = client.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        timeout=TOKEN_TIMEOUT,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError(f"Token não retornado para escopo {scope}")
    return str(token)


def _check_api(client: httpx.Client, *, url: str, token: str, label: str) -> dict[str, Any]:
    response = client.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=API_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    count = len(payload.get("value", [])) if isinstance(payload, dict) else 0
    return {"status": "PASS", "http_status": response.status_code, "items_observed": count, "check": label}


def run() -> dict[str, Any]:
    tenant_id, client_id, client_secret = _required_env()
    checks: list[dict[str, Any]] = []
    with httpx.Client(follow_redirects=True) as client:
        power_token = _token(
            client,
            tenant_id,
            client_id,
            client_secret,
            "https://api.powerplatform.com/.default",
        )
        checks.append({"status": "PASS", "check": "powerplatform_token"})
        checks.append(
            _check_api(
                client,
                url=POWER_PLATFORM_ENVIRONMENTS_URL,
                token=power_token,
                label="powerplatform_environments",
            )
        )

        graph_token = _token(
            client,
            tenant_id,
            client_id,
            client_secret,
            "https://graph.microsoft.com/.default",
        )
        checks.append({"status": "PASS", "check": "graph_token"})
        checks.append(_check_api(client, url=GRAPH_GROUPS_URL, token=graph_token, label="graph_groups"))

    return {"status": "PASS", "checks": checks}


def main() -> int:
    try:
        result = run()
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    except httpx.HTTPStatusError as exc:
        response = exc.response
        failure = {
            "status": "FAIL",
            "stage": "microsoft_http",
            "http_status": response.status_code,
            "request_url": str(response.request.url).split("?")[0],
        }
        print(json.dumps(failure, ensure_ascii=False, separators=(",", ":")))
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "stage": "runtime", "error_type": type(exc).__name__, "message": str(exc)[:240]},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 3


if __name__ == "__main__":
    sys.exit(main())
