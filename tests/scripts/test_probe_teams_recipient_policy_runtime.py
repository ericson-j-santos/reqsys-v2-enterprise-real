from __future__ import annotations

from io import BytesIO
import json
from urllib.error import HTTPError

from scripts.probe_teams_recipient_policy_runtime import build_report, probe_policy


class _Response:
    def __init__(self, payload: dict, status: int = 200):
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_probe_confirma_endpoint_e_dry_run() -> None:
    def opener(request, timeout):
        assert request.full_url.endswith(
            "/v1/teams-gateway/recipient-policies/hitl-approvers/messages"
        )
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["dry_run"] is True
        assert payload["permitir_fallback"] is False
        return _Response({"success": True, "data": {"dry_run": True, "entregue": False}})

    result = probe_policy(
        base_url="https://reqsys-api.fly.dev",
        policy="hitl-approvers",
        opener=opener,
    )

    assert result["endpoint_available"] is True
    assert result["dry_run_confirmed"] is True
    assert result["policy_ready"] is True
    assert result["legacy_fallback_required"] is False
    assert result["fallback_retirement_candidate"] is True


def test_probe_http_200_sem_confirmacao_nao_declara_prontidao() -> None:
    def opener(request, timeout):
        return _Response({"success": True, "data": {"entregue": False}})

    result = probe_policy(
        base_url="https://reqsys-api.fly.dev",
        policy="hitl-approvers",
        opener=opener,
    )

    assert result["endpoint_available"] is True
    assert result["dry_run_confirmed"] is False
    assert result["policy_ready"] is False
    assert result["legacy_fallback_required"] is True


def test_probe_404_mantem_fallback_legado() -> None:
    def opener(request, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            BytesIO(b'{"detail":"Not Found"}'),
        )

    result = probe_policy(
        base_url="https://reqsys-api.fly.dev",
        policy="reqsys-operations",
        opener=opener,
    )

    assert result["endpoint_available"] is False
    assert result["status_code"] == 404
    assert result["error"] == "http_404"
    assert result["legacy_fallback_required"] is True
    assert result["production_touched"] is False


def test_report_exige_todas_as_politicas_prontas() -> None:
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return _Response({"success": True, "data": {"dry_run": True}})
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            BytesIO(b'{"detail":"Not Found"}'),
        )

    report = build_report(
        base_url="https://reqsys-api.fly.dev",
        policies=["hitl-approvers", "reqsys-operations"],
        opener=opener,
    )

    assert report["summary"] == {
        "policies_checked": 2,
        "endpoint_available": 1,
        "dry_run_confirmed": 1,
        "ready_policies": 1,
        "legacy_fallback_required": 1,
        "all_policies_ready": False,
    }
    assert report["decision"] == "keep_legacy_fallback"
    assert report["automatic_change_allowed"] is False
    assert report["production_touched"] is False
