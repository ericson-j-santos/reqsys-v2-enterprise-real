from __future__ import annotations

import base64
import json
import os
from unittest.mock import patch

import pytest

from scripts import powerbi_dre_sentinel_dev as m


WS = "11111111-1111-1111-1111-111111111111"
MODEL = "22222222-2222-2222-2222-222222222222"
DATASET = MODEL


def _definition():
    return {"definition": {"format": "TMSL", "parts": m._parts()}}


class FakeRequester:
    def __init__(
        self,
        *,
        existing=False,
        duplicate=False,
        mismatch=False,
        create_status=201,
        query_value=0,
        query_status=200,
        negative_status=400,
    ):
        self.exists = existing
        self.duplicate = duplicate
        self.mismatch = mismatch
        self.create_status = create_status
        self.query_value = query_value
        self.query_status = query_status
        self.negative_status = negative_status
        self.create_calls = 0
        self.calls = []

    def __call__(self, method, url, token, payload):
        self.calls.append((method, url, payload))
        if url.startswith(m.FABRIC_BASE + "/workspaces?roles="):
            role = url.rsplit("=", 1)[-1]
            values = [{"id": WS, "displayName": m.WORKSPACE_NAME}] if role == "Contributor" else []
            return 200, {}, {"value": values}
        if url == m.POWERBI_BASE + "/groups?$top=100&$skip=0":
            return 200, {}, {"value": [{
                "id": WS,
                "name": m.WORKSPACE_NAME,
                "isOnDedicatedCapacity": False,
                "isReadOnly": False,
            }]}
        if url == f"{m.FABRIC_BASE}/workspaces/{WS}/semanticModels" and method == "GET":
            values = []
            if self.exists:
                values.append({"id": MODEL, "displayName": m.CANARY_NAME, "type": "SemanticModel"})
                if self.duplicate:
                    values.append({
                        "id": "33333333-3333-3333-3333-333333333333",
                        "displayName": m.CANARY_NAME,
                        "type": "SemanticModel",
                    })
            return 200, {}, {"value": values}
        if url == f"{m.FABRIC_BASE}/workspaces/{WS}/semanticModels" and method == "POST":
            self.create_calls += 1
            if self.create_status != 201:
                return self.create_status, {}, {"error": {"errorCode": "LicenseOrCapacityBlocked"}}
            self.exists = True
            return 201, {}, {"id": MODEL, "displayName": m.CANARY_NAME}
        if url == f"{m.FABRIC_BASE}/workspaces/{WS}/semanticModels/{MODEL}/getDefinition?format=TMSL":
            if self.mismatch:
                parts = m._parts()
                model = json.loads(base64.b64decode(parts[1]["payload"]))
                model["model"]["tables"][0]["measures"][0]["expression"] = "1"
                parts[1]["payload"] = base64.b64encode(
                    json.dumps(model).encode("utf-8")
                ).decode("ascii")
                return 200, {}, {"definition": {"parts": parts}}
            return 200, {}, _definition()
        if url == f"{m.POWERBI_BASE}/groups/{WS}/datasets":
            values = [{"id": DATASET, "name": m.CANARY_NAME}] if self.exists else []
            return 200, {}, {"value": values}
        if url == f"{m.POWERBI_BASE}/groups/{WS}/datasets/{DATASET}/executeQueries":
            query = payload["queries"][0]["query"]
            if "Inexistente" in query:
                return self.negative_status, {}, {"error": {"code": "DAX query failure"}}
            if self.query_status != 200:
                return self.query_status, {}, {"error": {"code": "ExecuteQueriesDisabled"}}
            return 200, {}, {"results": [{"tables": [{"rows": [{"[value]": self.query_value}]}]}]}
        raise AssertionError((method, url))


def _run(fake):
    with patch.dict(os.environ, {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "a" * 40,
    }, clear=False), patch.object(m, "_az_tsv") as az, patch.object(m, "_token", side_effect=["fabric", "pbi"]):
        az.return_value = m.EXPECTED_TENANT
        return m.execute(
            tenant_id=m.EXPECTED_TENANT,
            authorization=m.AUTHORIZATION,
            requester=fake,
        )


def test_parts_are_minimal_tmsl_with_constant_meta():
    parts = m._parts()
    assert [p["path"] for p in parts] == ["definition.pbism", "model.bim"]
    assert all(p["payloadType"] == "InlineBase64" for p in parts)
    decoded = m._decode_parts({"definition": {"parts": parts}})
    model = decoded["model.bim"]["model"]
    table = model["tables"][0]
    assert table["name"] == "_Medidas"
    assert table["measures"] == [{"name": "Meta", "expression": "0", "formatString": "0"}]
    assert m._verify_definition({"definition": {"parts": parts}})


def test_positive_create_readback_query_negative_and_replay():
    fake = FakeRequester()
    result = _run(fake)
    assert result["status"] == "passed"
    assert result["semantic_model_created"] is True
    assert result["semantic_model_definition_verified"] is True
    assert result["idempotency_verified"] is True
    assert result["sentinel_value"] == 0
    assert result["sentinel_parity_passed"] is True
    assert result["negative_control_detected"] is True
    assert result["workspace_shared_capacity"] is True
    assert result["new_capacity_or_license_requested"] is False
    assert result["billing_mutation_performed"] is False
    assert result["incremental_cost_verified_zero"] is False
    assert result["metric_parity_promoted"] is False
    assert fake.create_calls == 1
    serialized = json.dumps(result)
    assert WS not in serialized
    assert MODEL not in serialized
    assert m.WORKSPACE_NAME not in serialized
    assert m.CANARY_NAME not in serialized


def test_existing_matching_canary_is_reused_without_write():
    fake = FakeRequester(existing=True)
    result = _run(fake)
    assert result["semantic_model_created"] is False
    assert result["idempotency_verified"] is True
    assert fake.create_calls == 0


def test_existing_mismatched_canary_blocks_without_update_or_delete():
    fake = FakeRequester(existing=True, mismatch=True)
    with pytest.raises(m.CanaryError, match="existing_canary_definition_mismatch"):
        _run(fake)
    assert fake.create_calls == 0
    assert not any("/updateDefinition" in url for _, url, _ in fake.calls)
    assert not any(method == "DELETE" for method, _, _ in fake.calls)


def test_duplicate_canary_blocks_before_write():
    fake = FakeRequester(existing=True, duplicate=True)
    with pytest.raises(m.CanaryError, match="canary_ambiguous_2"):
        _run(fake)
    assert fake.create_calls == 0


def test_license_or_capacity_rejection_fails_without_purchase_fallback():
    fake = FakeRequester(create_status=403)
    with pytest.raises(m.CanaryError, match="create_semantic_model_http_403"):
        _run(fake)
    assert fake.create_calls == 1
    assert not any("capacities" in url.casefold() for _, url, _ in fake.calls)
    assert not any("license" in url.casefold() for _, url, _ in fake.calls)


def test_execute_queries_failure_does_not_promote_parity():
    fake = FakeRequester(query_status=403)
    with pytest.raises(m.CanaryError, match="execute_queries_http_403"):
        _run(fake)


def test_sentinel_divergence_is_detected():
    fake = FakeRequester(query_value=1)
    with pytest.raises(m.CanaryError, match="sentinel_value_mismatch"):
        _run(fake)


def test_negative_control_must_be_rejected():
    fake = FakeRequester(negative_status=200)
    with pytest.raises(m.CanaryError, match="negative_control_failed"):
        _run(fake)


def test_main_dispatch_and_literal_authorization_are_mandatory():
    with patch.dict(os.environ, {
        "GITHUB_REF": "refs/heads/feature",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
    }, clear=False):
        with pytest.raises(m.CanaryError, match="main_required"):
            m.execute(tenant_id=m.EXPECTED_TENANT, authorization=m.AUTHORIZATION)
    with patch.dict(os.environ, {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "pull_request",
    }, clear=False):
        with pytest.raises(m.CanaryError, match="workflow_dispatch_required"):
            m.execute(tenant_id=m.EXPECTED_TENANT, authorization=m.AUTHORIZATION)
    with patch.dict(os.environ, {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
    }, clear=False):
        with pytest.raises(m.CanaryError, match="authorization_invalid"):
            m.execute(tenant_id=m.EXPECTED_TENANT, authorization="wrong")


def test_source_has_no_delete_update_refresh_billing_or_prod_route():
    text = Path(m.__file__).read_text(encoding="utf-8")
    lowered = text.casefold()
    assert 'method="delete"' not in lowered
    assert '"delete"' not in lowered
    assert "/updatedefinition" not in lowered
    assert "/refreshes" not in lowered
    assert "/capacities" not in lowered
    assert "purchase" not in lowered
    assert "production_touched" in text
    assert "stg_hml_touched" in text
