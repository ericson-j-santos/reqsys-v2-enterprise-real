from __future__ import annotations

import json
import subprocess
import time
import urllib.request

ALERT_NAME = "EnvironmentObservabilityApiUnavailableDev"
COMPOSE = ["docker", "compose", "-f", "compose.observability.dev.yml"]


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_alert(active: bool, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        alerts = get_json("http://127.0.0.1:9093/api/v2/alerts")
        found = any(
            item.get("labels", {}).get("alertname") == ALERT_NAME
            and item.get("status", {}).get("state") == "active"
            for item in alerts
        )
        if found is active:
            return
        time.sleep(3)
    state = "firing" if active else "resolved"
    raise RuntimeError(f"Alerta {ALERT_NAME} não atingiu estado {state}")


def main() -> None:
    subprocess.run(COMPOSE + ["stop", "api"], check=True)
    wait_for_alert(True)
    subprocess.run(COMPOSE + ["start", "api"], check=True)
    wait_for_alert(False)
    print(json.dumps({"status": "ok", "alert": ALERT_NAME, "firing": True, "resolved": True}))


if __name__ == "__main__":
    main()
