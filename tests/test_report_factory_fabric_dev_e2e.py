import base64
import io
import importlib.util
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "report_factory_fabric_dev_e2e.py"

SPEC = importlib.util.spec_from_file_location("report_factory_fabric_dev_e2e", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_exact_by_display_name_is_fail_closed_for_ambiguity() -> None:
    rows = [{"displayName": "A"}, {"displayName": "A"}]
    with pytest.raises(module.E2EError, match="report_ambiguous:2"):
        module._exact_by_display_name(rows, "A", "report")


def test_exact_by_display_name_returns_zero_or_one() -> None:
    rows = [{"displayName": "A"}, {"displayName": "B"}]
    assert module._exact_by_display_name(rows, "C", "report") == []
    assert module._exact_by_display_name(rows, "B", "report") == [{"displayName": "B"}]


def test_extract_rdl_requires_exact_inline_base64_part() -> None:
    rdl = "<?xml version='1.0'?><Report />"
    body = {
        "definition": {
            "parts": [{
                "path": "DemandasPorStatus.rdl",
                "payload": base64.b64encode(rdl.encode("utf-8")).decode("ascii"),
                "payloadType": "InlineBase64",
            }]
        }
    }
    assert module._extract_rdl(body, "DemandasPorStatus") == rdl


def test_extract_rdl_rejects_wrong_or_duplicate_part() -> None:
    payload = base64.b64encode(b"<Report />").decode("ascii")
    with pytest.raises(module.E2EError, match="rdl_part_exact_count:0"):
        module._extract_rdl(
            {"definition": {"parts": [{"path": "Other.rdl", "payload": payload, "payloadType": "InlineBase64"}]}},
            "DemandasPorStatus",
        )
    with pytest.raises(module.E2EError, match="rdl_part_exact_count:2"):
        module._extract_rdl(
            {"definition": {"parts": [
                {"path": "DemandasPorStatus.rdl", "payload": payload, "payloadType": "InlineBase64"},
                {"path": "DemandasPorStatus.rdl", "payload": payload, "payloadType": "InlineBase64"},
            ]}},
            "DemandasPorStatus",
        )


def test_operation_id_can_be_derived_without_persisting_url() -> None:
    assert module._operation_id(
        {"x-ms-operation-id": "op-123"},
        "https://api.fabric.microsoft.com/v1/operations/op-123",
    ) == "op-123"
    assert module._operation_id(
        {},
        "https://api.fabric.microsoft.com/v1/operations/op-456",
    ) == "op-456"


def test_script_has_fixed_dev_boundary_and_no_prod_target() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'WORKSPACE_NAME = "ReqSys - Observabilidade"' in text
    assert 'ENVIRONMENT = "development"' in text
    assert 'os.getenv("GITHUB_REF") != "refs/heads/main"' in text
    assert '"production_touched": False' in text
    assert "client-secret" not in text
    assert "environment=prod" not in text
    assert "environment=stg" not in text

def test_safe_fabric_error_code_extracts_only_structured_code() -> None:
    raw = '{"errorCode":"CorruptedPayload","message":"token=should-not-leak"}'
    assert module._safe_fabric_error_code(raw) == "CorruptedPayload"
    assert module._safe_fabric_error_code('{"error":{"code":"InvalidItem","message":"sensitive"}}') == "InvalidItem"
    assert module._safe_fabric_error_code('{"message":"no structured code"}') == "unknown"


def test_safe_fabric_error_codes_preserves_nested_codes_without_messages() -> None:
    raw = (
        '{"errorCode":"InvalidDefinitionFormat","message":"token=should-not-leak",'
        '"moreDetails":[{"errorCode":"RdlSchemaError","message":"secret detail"},'
        '{"error":{"code":"InvalidElement","message":"another secret"}}]}'
    )
    assert module._safe_fabric_error_codes(raw) == [
        "InvalidDefinitionFormat",
        "RdlSchemaError",
        "InvalidElement",
    ]


def test_safe_fabric_rdl_diagnostics_extracts_only_allowlisted_schema_context() -> None:
    raw = (
        '{"errorCode":"InvalidDefinitionFormat",'
        '"message":"Element ReportParametersLayout is invalid at line 42 position 7; '
        'password=123456; https://internal.example.invalid",'
        '"parameters":[{"name":"elementName","value":"Tablix"},'
        '{"name":"requestId","value":"secret-identifier-999"}]}'
    )
    assert module._safe_fabric_rdl_diagnostics(raw) == [
        "rdl_ReportParametersLayout",
        "line_42",
        "position_7",
        "rdl_Tablix",
    ]


def test_request_json_http_error_exposes_safe_rdl_context_not_message() -> None:
    body = (
        b'{"errorCode":"InvalidDefinitionFormat",'
        b'"message":"Invalid ReportParametersLayout at line 42 column 9; token=should-not-leak"}'
    )
    error = urllib.error.HTTPError(
        module.FABRIC_BASE + "/workspaces/example/paginatedReports",
        400,
        "Bad Request",
        hdrs=None,
        fp=io.BytesIO(body),
    )
    with patch.object(module.urllib.request, "urlopen", side_effect=error):
        with pytest.raises(module.E2EError) as captured:
            module._request_json(
                "POST",
                module.FABRIC_BASE + "/workspaces/example/paginatedReports",
                "ephemeral-token",
                {"displayName": "Example"},
            )

    reason = str(captured.value)
    assert reason == (
        "fabric_http_400:InvalidDefinitionFormat:"
        "rdl_ReportParametersLayout:line_42:column_9"
    )
    assert "should-not-leak" not in reason
    assert "ephemeral-token" not in reason


def test_request_json_http_error_exposes_code_not_body() -> None:
    body = b'{"errorCode":"CorruptedPayload","message":"token=should-not-leak"}'
    error = urllib.error.HTTPError(
        module.FABRIC_BASE + "/workspaces/example/paginatedReports",
        400,
        "Bad Request",
        hdrs=None,
        fp=io.BytesIO(body),
    )
    with patch.object(module.urllib.request, "urlopen", side_effect=error):
        with pytest.raises(module.E2EError) as captured:
            module._request_json(
                "POST",
                module.FABRIC_BASE + "/workspaces/example/paginatedReports",
                "ephemeral-token",
                {"displayName": "Example"},
            )

    reason = str(captured.value)
    assert reason == "fabric_http_400:CorruptedPayload"
    assert "should-not-leak" not in reason
    assert "ephemeral-token" not in reason


def test_request_json_http_error_exposes_nested_codes_not_messages() -> None:
    body = (
        b'{"errorCode":"InvalidDefinitionFormat","message":"token=should-not-leak",'
        b'"moreDetails":[{"errorCode":"RdlSchemaError","message":"secret detail"}]}'
    )
    error = urllib.error.HTTPError(
        module.FABRIC_BASE + "/workspaces/example/paginatedReports",
        400,
        "Bad Request",
        hdrs=None,
        fp=io.BytesIO(body),
    )
    with patch.object(module.urllib.request, "urlopen", side_effect=error):
        with pytest.raises(module.E2EError) as captured:
            module._request_json(
                "POST",
                module.FABRIC_BASE + "/workspaces/example/paginatedReports",
                "ephemeral-token",
                {"displayName": "Example"},
            )

    reason = str(captured.value)
    assert reason == "fabric_http_400:InvalidDefinitionFormat:RdlSchemaError"
    assert "should-not-leak" not in reason
    assert "secret detail" not in reason
    assert "ephemeral-token" not in reason

def _generated_example_rdl() -> str:
    spec_path = ROOT / "examples" / "report-factory" / "demandas_por_status.json"
    source = module.report_factory.load_spec(spec_path)
    return module.report_factory.generate_rdl(source)


def test_staged_rdl_variants_isolate_layers_without_auxiliary_reports() -> None:
    rdl = _generated_example_rdl()
    variants = dict(module._staged_rdl_variants(rdl))

    assert list(variants) == [
        "layout",
        "datasource",
        "dataset_parameters",
        "full",
    ]
    assert variants["full"] == rdl

    layout = ET.fromstring(variants["layout"])
    assert layout.find(module.report_factory._q("DataSources")) is None
    assert layout.find(module.report_factory._q("DataSets")) is None
    assert layout.find(module.report_factory._q("ReportParameters")) is None
    assert layout.find(module.report_factory._q("ReportParametersLayout")) is None
    assert not layout.findall(f".//{module.report_factory._q('Tablix')}")

    datasource = ET.fromstring(variants["datasource"])
    assert datasource.find(module.report_factory._q("DataSources")) is not None
    assert datasource.find(module.report_factory._q("DataSets")) is None
    assert datasource.find(module.report_factory._q("ReportParameters")) is None
    assert not datasource.findall(f".//{module.report_factory._q('Tablix')}")

    dataset = ET.fromstring(variants["dataset_parameters"])
    assert dataset.find(module.report_factory._q("DataSources")) is not None
    assert dataset.find(module.report_factory._q("DataSets")) is not None
    assert dataset.find(module.report_factory._q("ReportParameters")) is not None
    assert dataset.find(module.report_factory._q("ReportParametersLayout")) is not None
    assert not dataset.findall(f".//{module.report_factory._q('Tablix')}")


def test_staged_rdl_variants_fail_closed_for_invalid_xml() -> None:
    with pytest.raises(module.E2EError, match="definition_probe_rdl_invalid"):
        module._staged_rdl_variants("<Report>")


def test_invalid_definition_classifier_is_specific() -> None:
    assert module._is_invalid_definition_format(
        module.E2EError("fabric_http_400:InvalidDefinitionFormat")
    )
    assert not module._is_invalid_definition_format(
        module.E2EError("fabric_http_403:Forbidden")
    )


def test_definition_probe_confirms_each_stage_by_independent_readback() -> None:
    rdl = _generated_example_rdl()
    current: dict[str, object] = {"definition": None}
    updates: list[dict] = []

    def fake_update(
        workspace_id: str,
        report_id: str,
        definition: dict,
        token: str,
    ) -> None:
        assert workspace_id == "workspace-1"
        assert report_id == "report-1"
        assert token == "token"
        current["definition"] = definition
        updates.append(definition)

    def fake_get_definition(
        workspace_id: str,
        report_id: str,
        token: str,
    ) -> dict:
        assert workspace_id == "workspace-1"
        assert report_id == "report-1"
        assert token == "token"
        definition = current["definition"]
        assert isinstance(definition, dict)
        return {"definition": definition}

    with (
        patch.object(module, "_update_definition", side_effect=fake_update),
        patch.object(module, "_get_definition", side_effect=fake_get_definition),
    ):
        result = module._run_definition_probe(
            reports_url=module.FABRIC_BASE + "/workspaces/workspace-1/paginatedReports",
            workspace_id="workspace-1",
            report_name="DemandasPorStatus",
            rdl=rdl,
            token="token",
            existing_report_id="report-1",
        )

    assert result["failed_stage"] is None
    assert result["stages_passed"] == [
        "layout",
        "datasource",
        "dataset_parameters",
        "full",
    ]
    assert result["created"] is False
    assert result["report_id"] == "report-1"
    assert len(updates) == 4


def test_definition_probe_stops_at_first_invalid_layer() -> None:
    rdl = _generated_example_rdl()
    current: dict[str, object] = {"definition": None}
    calls = 0

    def fake_update(
        workspace_id: str,
        report_id: str,
        definition: dict,
        token: str,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise module.E2EError("fabric_http_400:InvalidDefinitionFormat")
        current["definition"] = definition

    def fake_get_definition(
        workspace_id: str,
        report_id: str,
        token: str,
    ) -> dict:
        definition = current["definition"]
        assert isinstance(definition, dict)
        return {"definition": definition}

    with (
        patch.object(module, "_update_definition", side_effect=fake_update),
        patch.object(module, "_get_definition", side_effect=fake_get_definition),
    ):
        result = module._run_definition_probe(
            reports_url=module.FABRIC_BASE + "/workspaces/workspace-1/paginatedReports",
            workspace_id="workspace-1",
            report_name="DemandasPorStatus",
            rdl=rdl,
            token="token",
            existing_report_id="report-1",
        )

    assert result["stages_passed"] == ["layout"]
    assert result["failed_stage"] == "datasource"
    assert result["reason"] == "fabric_http_400:InvalidDefinitionFormat"
    assert calls == 2

