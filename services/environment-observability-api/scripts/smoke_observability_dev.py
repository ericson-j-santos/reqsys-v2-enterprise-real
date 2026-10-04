from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

RETRY_INTERVAL_SECONDS = 1
STARTUP_TIMEOUT_SECONDS = 45


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def get_json(url: str) -> dict[str, Any]:
    return json.loads(get_text(url))


def wait_for_text(url: str, timeout_seconds: int = STARTUP_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            get_text(url)
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(RETRY_INTERVAL_SECONDS)
    raise RuntimeError(f"Timeout aguardando {url}: {last_error}")


def wait_for_json(
    url: str,
    predicate: Callable[[dict[str, Any]], bool],
    timeout_seconds: int = STARTUP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            payload = get_json(url)
            if predicate(payload):
                return payload
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
        time.sleep(RETRY_INTERVAL_SECONDS)
    raise RuntimeError(f"Timeout aguardando {url}: {last_error}")


def main() -> None:
    wait_for_json("http://127.0.0.1:8000/health", lambda payload: payload.get("status") == "healthy")
    wait_for_text("http://127.0.0.1:9090/-/ready")
    wait_for_text("http://127.0.0.1:9093/-/ready")
    wait_for_json("http://127.0.0.1:3000/api/health", lambda payload: payload.get("database") == "ok")

    for _ in range(5):
        get_json("http://127.0.0.1:8000/health")

    query = urllib.parse.quote('environment_observability_http_requests_total{environment="development"}')
    metrics = wait_for_json(
        f"http://127.0.0.1:9090/api/v1/query?query={query}",
        lambda payload: payload.get("status") == "success"
        and bool(payload.get("data", {}).get("result")),
    )

    rules = get_json("http://127.0.0.1:9090/api/v1/rules")
    groups = rules.get("data", {}).get("groups", [])
    if not groups:
        raise RuntimeError("Prometheus não carregou regras de alerta")

    print(
        json.dumps(
            {
                "status": "ok",
                "metrics_samples": len(metrics["data"]["result"]),
                "rule_groups": len(groups),
            }
        )
    )


if __name__ == "__main__":
    main()
