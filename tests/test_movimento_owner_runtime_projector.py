from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path("scripts/movimento_owner_runtime_projector.py")
SPEC = importlib.util.spec_from_file_location("movimento_owner_runtime_projector", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def health_payload() -> dict:
    return {"data": {"status": "ok"}}


def runtime_payload() -> dict:
    return {
        "data": {
            "status": "healthy",
            "status_raw": "degraded",
            "risk_score": 15,
            "uptime_seconds": 123.9,
            "runtime_health": {"score_global": 66},
            "critical_counts": {
                "pending_items": 4,
                "blocked_items": 0,
            },
        }
    }


def test_build_owner_payload_uses_only_real_runtime_metrics() -> None:
    payload = module.build_owner_payload(
        data_referencia="2026-09-19",
        health=health_payload(),
        runtime=runtime_payload(),
        correlation_id="corr-1",
    )

    datasets = payload["datasets"]
    fechamento = datasets["fechamento_diario"]

    assert len(fechamento) == 8
    assert datasets["pendencias_cadastro"] == []
    assert datasets["pendencias_historicas"] == []
    assert datasets["pendencias_observacao"] == []
    assert {item["indicador"] for item in fechamento} == {
        "reqsys_api_status",
        "reqsys_runtime_status",
        "reqsys_runtime_status_raw",
        "reqsys_runtime_risk_score",
        "reqsys_runtime_uptime_seconds",
        "reqsys_runtime_score_global",
        "reqsys_runtime_pending_items",
        "reqsys_runtime_blocked_items",
    }
    assert all(item["data_referencia"] == "2026-09-19" for item in fechamento)
    assert all("não representa transação comercial" in item["observacao"] for item in fechamento)


def test_build_owner_payload_preserves_observed_values() -> None:
    payload = module.build_owner_payload(
        data_referencia="2026-09-19",
        health=health_payload(),
        runtime=runtime_payload(),
        correlation_id="corr-2",
    )

    values = {item["indicador"]: item["valor"] for item in payload["datasets"]["fechamento_diario"]}
    assert values["reqsys_api_status"] == "ok"
    assert values["reqsys_runtime_status"] == "healthy"
    assert values["reqsys_runtime_status_raw"] == "degraded"
    assert values["reqsys_runtime_risk_score"] == "15"
    assert values["reqsys_runtime_uptime_seconds"] == "123"
    assert values["reqsys_runtime_score_global"] == "66"
    assert values["reqsys_runtime_pending_items"] == "4"
    assert values["reqsys_runtime_blocked_items"] == "0"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("data", "status"), None),
        (("data", "risk_score"), None),
        (("data", "runtime_health", "score_global"), None),
        (("data", "critical_counts", "pending_items"), None),
    ],
)
def test_build_owner_payload_fails_closed_on_missing_metric(path: tuple[str, ...], value) -> None:
    health = health_payload()
    runtime = runtime_payload()
    target = health if path[0] == "health" else runtime
    keys = path if path[0] != "health" else path[1:]
    if path[0] == "data" and path[1] == "status":
        health["data"]["status"] = value
    else:
        current = target
        for key in keys[:-1]:
            current = current[key]
        current[keys[-1]] = value

    with pytest.raises(RuntimeError, match="runtime_metric_missing"):
        module.build_owner_payload(
            data_referencia="2026-09-19",
            health=health,
            runtime=runtime,
            correlation_id="corr-3",
        )
