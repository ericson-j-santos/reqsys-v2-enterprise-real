from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read().decode("utf-8")


def get_json(url: str) -> dict:
    return json.loads(get_text(url))


def wait_for_text(url: str, timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            get_text(url)
            return
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f"Timeout aguardando {url}: {last_error}")


def wait_for_json(url: str, predicate, timeout_seconds: int = 120) -> dict:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            payload = get_json(url)
            if predicate(payload):
                return payload
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f"Timeout aguardando {url}: {last_error}")


def main() -> None:
    wait_for_json("http://127.0.0.1:8000/health", lambda p: p.get("status") == "healthy")
    wait_for_text("http://127.0.0.1:9090/-/ready")
    wait_for_text("http://127.0.0.1:9093/-/ready")
    wait_for_json("http://127.0.0.1:3000/api/health", lambda p: p.get("database") == "ok")

    for _ in range(5):
        get_json("http://127.0.0.1:8000/health")

    query = urllib.parse.quote('environment_observability_http_requests_total{environment="development"}')
    metrics = wait_for_json(
        f"http://127.0.0.1:9090/api/v1/query?query={query}",
        lambda p: p.get("status") == "success" and bool(p.get("data", {}).get("result")),
    )

    rules = get_json("http://127.0.0.1:9090/api/v1/rules")
    groups = rules.get("data", {}).get("groups", [])
    if not groups:
        raise RuntimeError("Prometheus não carregou regras de alerta")

    print(json.dumps({"status": "ok", "metrics_samples": len(metrics["data"]["result"]), "rule_groups": len(groups)}))


if __name__ == "__main__":
    main()
