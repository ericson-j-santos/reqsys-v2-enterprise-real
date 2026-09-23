import base64
import io
import importlib.util
import urllib.error
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



def _generated_rdl() -> str:
    spec = module.report_factory.load_spec(
        ROOT / "examples" / "report-factory" / "demandas_por_status.json"
    )
    module.report_factory.validate_spec(spec)
    return module.report_factory.generate_rdl(spec)


def _contains(rdl: str, name: str) -> bool:
    root = module.ET.fromstring(rdl)
    return root.find(f".//{module.report_factory._q(name)}") is not None


@pytest.mark.parametrize(
    ("stage", "expected", "absent"),
    [
        ("minimal", (), ("DataSources", "DataSets", "ReportParameters", "Tablix")),
        ("datasource", ("DataSources",), ("DataSets", "ReportParameters", "Tablix")),
        ("parameters", ("ReportParameters", "ReportParametersLayout"), ("DataSources", "DataSets", "Tablix")),
        ("data_model", ("DataSources", "DataSets", "ReportParameters", "ReportParametersLayout"), ("Tablix",)),
    ],
)
def test_probe_rdl_decomposes_definition_without_touching_full(
    stage: str, expected: tuple[str, ...], absent: tuple[str, ...]
) -> None:
    full = _generated_rdl()
    variant = module._build_probe_rdl(full, stage)
    for name in expected:
        assert _contains(variant, name)
    for name in absent:
        assert not _contains(variant, name)
    assert module._build_probe_rdl(full, "full") == full


@pytest.mark.parametrize(
    ("results", "component"),
    [
        ({"minimal": "fabric_http_400:InvalidDefinitionFormat"}, "base_rdl"),
        (
            {
                "minimal": "passed",
                "datasource": "fabric_http_400:InvalidDefinitionFormat",
                "parameters": "passed",
                "data_model": "fabric_http_400:InvalidDefinitionFormat",
                "full": "fabric_http_400:InvalidDefinitionFormat",
            },
            "datasource",
        ),
        (
            {
                "minimal": "passed",
                "datasource": "passed",
                "parameters": "fabric_http_400:InvalidDefinitionFormat",
                "data_model": "fabric_http_400:InvalidDefinitionFormat",
                "full": "fabric_http_400:InvalidDefinitionFormat",
            },
            "parameters",
        ),
        (
            {
                "minimal": "passed",
                "datasource": "passed",
                "parameters": "passed",
                "data_model": "fabric_http_400:InvalidDefinitionFormat",
                "full": "fabric_http_400:InvalidDefinitionFormat",
            },
            "dataset_or_cross_component",
        ),
        (
            {
                "minimal": "passed",
                "datasource": "passed",
                "parameters": "passed",
                "data_model": "passed",
                "full": "fabric_http_400:InvalidDefinitionFormat",
            },
            "tablix",
        ),
        (
            {
                "minimal": "passed",
                "datasource": "passed",
                "parameters": "passed",
                "data_model": "passed",
                "full": "passed",
            },
            "main_request_context",
        ),
    ],
)
def test_infer_probe_component(results: dict[str, str], component: str) -> None:
    assert module._infer_probe_component(results) == component


def test_probe_name_contains_only_safe_characters() -> None:
    with patch.dict(module.os.environ, {"GITHUB_RUN_ID": "35866066425", "GITHUB_SHA": "abc12345def"}):
        name = module._probe_name("data_model")
    assert name.startswith("ReqSysRdlProbe")
    assert name.isalnum()
    assert len(name) <= 120
