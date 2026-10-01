from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx

from app.services.microsoft_oauth import MicrosoftOAuthError

TOKEN_TIMEOUT = 20.0
API_TIMEOUT = 30.0
POWER_PLATFORM_ENVIRONMENTS_URL = (
    "https://api.powerplatform.com/environmentmanagement/environments"
    "?api-version=2024-10-01"
)


def _required_env() -> dict[str, str]:
    values = {
        "POWER_PLATFORM_TENANT_ID": os.getenv("POWER_PLATFORM_TENANT_ID", "").strip(),
        "POWER_PLATFORM_CLIENT_ID": os.getenv("POWER_PLATFORM_CLIENT_ID", "").strip(),
        "POWER_PLATFORM_CLIENT_SECRET": os.getenv("POWER_PLATFORM_CLIENT_SECRET", "").strip(),
        "DATAVERSE_TENANT_ID": os.getenv("DATAVERSE_TENANT_ID", "").strip(),
        "DATAVERSE_CLIENT_ID": os.getenv("DATAVERSE_CLIENT_ID", "").strip(),
        "DATAVERSE_CLIENT_SECRET": os.getenv("DATAVERSE_CLIENT_SECRET", "").strip(),
        "DATAVERSE_ENVIRONMENT_URL": os.getenv("DATAVERSE_ENVIRONMENT_URL", "").strip().rstrip("/"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("Variáveis Microsoft ausentes: " + ", ".join(missing))
    if not values["DATAVERSE_ENVIRONMENT_URL"].lower().startswith("https://"):
        raise RuntimeError("DATAVERSE_ENVIRONMENT_URL deve usar HTTPS")
    return values


def _token(
    client: httpx.Client,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    scope: str,
    resource: str,
) -> str:
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
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise MicrosoftOAuthError.from_response(response, resource=resource) from exc
    token = response.json().get("access_token")
    if not token:
        raise MicrosoftOAuthError(
            resource=resource,
            status_code=response.status_code,
            error_code="access_token_missing",
        )
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
    config = _required_env()
    checks: list[dict[str, Any]] = []
    with httpx.Client(follow_redirects=True) as client:
        power_token = _token(
            client,
            config["POWER_PLATFORM_TENANT_ID"],
            config["POWER_PLATFORM_CLIENT_ID"],
            config["POWER_PLATFORM_CLIENT_SECRET"],
            "https://api.powerplatform.com/.default",
            "power_platform",
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

        dataverse_url = config["DATAVERSE_ENVIRONMENT_URL"]
        dataverse_token = _token(
            client,
            config["DATAVERSE_TENANT_ID"],
            config["DATAVERSE_CLIENT_ID"],
            config["DATAVERSE_CLIENT_SECRET"],
            f"{dataverse_url}/.default",
            "dataverse",
        )
        checks.append({"status": "PASS", "check": "dataverse_token"})
        checks.append(
            _check_api(
                client,
                url=f"{dataverse_url}/api/data/v9.2/WhoAmI",
                token=dataverse_token,
                label="dataverse_whoami",
            )
        )

    return {"status": "PASS", "checks": checks}


def main() -> int:
    try:
        result = run()
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    except MicrosoftOAuthError as exc:
        print(
            json.dumps(
                {"status": "FAIL", "stage": "oauth_token", "oauth_error": exc.as_dict()},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 2
    except httpx.HTTPStatusError as exc:
        response = exc.response
        failure = {
            "status": "FAIL",
            "stage": "resource_http",
            "http_status": response.status_code,
            "request_host": response.request.url.host,
        }
        print(json.dumps(failure, ensure_ascii=False, separators=(",", ":")))
        return 2
    except Exception as exc:  # noqa: BLE001 - ultimo limite do probe; resposta permanece sanitizada
        print(
            json.dumps(
                {"status": "FAIL", "stage": "runtime", "error_type": type(exc).__name__},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 3


if __name__ == "__main__":
    sys.exit(main())
