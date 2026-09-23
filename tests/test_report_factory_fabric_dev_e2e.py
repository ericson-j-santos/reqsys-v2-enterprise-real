import base64
import importlib.util
from pathlib import Path

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
