from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, Path(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


worker = load("scripts/movimento_owner_runtime_feed_worker.py", "owner_runtime_feed_worker")


class FakeProjector:
    def _get_json(self, url: str):
        if url.endswith("/api/health"):
            return {"data": {"status": "ok"}}
        return {
            "data": {
                "status": "healthy",
                "status_raw": "degraded",
                "risk_score": 15,
                "uptime_seconds": 123,
                "runtime_health": {"score_global": 66},
                "critical_counts": {"pending_items": 4, "blocked_items": 0},
            }
        }

    def build_owner_payload(self, *, data_referencia, health, runtime, correlation_id):
        return {
            "correlation_id": correlation_id,
            "data_referencia": data_referencia,
            "datasets": {
                "fechamento_diario": [
                    {
                        "indicador": "reqsys_api_status",
                        "valor": health["data"]["status"],
                        "observacao": "runtime real",
                        "data_referencia": data_referencia,
                    }
                ],
                "pendencias_cadastro": [],
                "pendencias_historicas": [],
                "pendencias_observacao": [],
            },
        }


def test_run_once_ingests_then_syncs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    owner_config = tmp_path / "config.json"
    owner_token = tmp_path / "service.token"
    owner_config.write_text('{"bind_ip":"100.80.1.2","port":18443}', encoding="utf-8")
    owner_token.write_text("x" * 48, encoding="utf-8")

    calls = []

    def fake_request(url, *, method, token, payload=None, timeout=15.0):
        calls.append((url, method, payload))
        if url.endswith("/ingest"):
            return {
                "status": "applied",
                "row_counts": {"fechamento_diario": 1},
                "write_count": 1,
            }
        return {
            "status": "applied",
            "row_counts": {
                "fechamento_diario": 1,
                "pendencias_cadastro": 0,
                "pendencias_historicas": 0,
                "pendencias_observacao": 0,
            },
            "write_count": 1,
        }

    monkeypatch.setattr(worker, "request_json", fake_request)
    result = worker.run_once(
        {
            "runtime_base": "http://DESKTOP-PDQK954:8081",
            "owner_config": str(owner_config),
            "owner_token_file": str(owner_token),
        },
        FakeProjector(),
    )

    assert result["status"] == "passed"
    assert result["ingest_status"] == "applied"
    assert result["sync_status"] == "applied"
    assert [call[0].rsplit("/", 1)[-1] for call in calls] == ["ingest", "sync"]
    assert result["synthetic"] is False
    assert result["business_transaction_claimed"] is False
    assert result["production_touched"] is False


def test_run_once_fails_closed_if_ingest_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    owner_config = tmp_path / "config.json"
    owner_token = tmp_path / "service.token"
    owner_config.write_text('{"bind_ip":"100.80.1.2","port":18443}', encoding="utf-8")
    owner_token.write_text("x" * 48, encoding="utf-8")

    monkeypatch.setattr(
        worker,
        "request_json",
        lambda *args, **kwargs: {"status": "blocked"},
    )

    with pytest.raises(RuntimeError, match="owner_ingest_failed"):
        worker.run_once(
            {
                "runtime_base": "http://DESKTOP-PDQK954:8081",
                "owner_config": str(owner_config),
                "owner_token_file": str(owner_token),
            },
            FakeProjector(),
        )


def test_worker_rejects_short_polling_interval() -> None:
    source = Path("scripts/movimento_owner_runtime_feed_worker.py").read_text(encoding="utf-8")
    assert "interval < 300" in source


def test_bootstrap_persists_without_embedding_secret() -> None:
    source = Path("scripts/bootstrap_movimento_owner_runtime_feed.py").read_text(encoding="utf-8")
    assert "CurrentVersion\\Run" in source
    assert "ReqSysOwnerRuntimeFeed" in source
    assert "OwnerGateway" in source
    assert "service.token" in source
    assert "Bearer " not in source
    assert "production_touched" in source
