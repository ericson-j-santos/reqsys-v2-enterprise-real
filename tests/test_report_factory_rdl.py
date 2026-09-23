from __future__ import annotations

import base64
import copy
import importlib.util
import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "geradores" / "report_factory.py"
SPEC_PATH = ROOT / "examples" / "report-factory" / "demandas_por_status.json"

spec = importlib.util.spec_from_file_location("report_factory", MODULE_PATH)
assert spec and spec.loader
report_factory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report_factory)


def load_example() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def test_spec_to_rdl_to_fabric_payload_e2e_local() -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    report_factory.validate_rdl(rdl, source)
    payload = report_factory.build_create_request(source, rdl)

    assert payload["displayName"] == "DemandasPorStatus"
    part = payload["definition"]["parts"][0]
    assert part["path"] == "DemandasPorStatus.rdl"
    assert part["payloadType"] == "InlineBase64"
    decoded = base64.b64decode(part["payload"]).decode("utf-8")
    assert decoded == rdl
    assert "dbo.tbDemandas" in decoded
    assert '=Parameters!DataInicio.Value' in decoded
    assert 'Name="DemandasPorStatusTable"' in decoded


def test_generation_is_deterministic_and_idempotent() -> None:
    source = load_example()
    first = report_factory.generate_rdl(source)
    second = report_factory.generate_rdl(copy.deepcopy(source))
    assert first == second


def test_rejects_embedded_credentials_before_rdl_generation() -> None:
    source = load_example()
    source["datasource"]["connect_string"] += ";User ID=sa;Password=should-not-exist"
    with pytest.raises(report_factory.ReportSpecError, match="credenciais|segredos"):
        report_factory.generate_rdl(source)


def test_rejects_component_pointing_to_unknown_dataset() -> None:
    source = load_example()
    source["components"][0]["dataset"] = "NaoExiste"
    with pytest.raises(report_factory.ReportSpecError, match="dataset inexistente"):
        report_factory.validate_spec(source)


def test_rejects_unsupported_component_fail_closed() -> None:
    source = load_example()
    source["components"][0]["type"] = "chart"
    with pytest.raises(report_factory.ReportSpecError, match="apenas component.type=table"):
        report_factory.validate_spec(source)

def test_parameterized_rdl_emits_required_rdl_2016_layout() -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    root = ET.fromstring(rdl)

    layout = root.find(report_factory._q("ReportParametersLayout"))
    assert layout is not None
    grid = layout.find(report_factory._q("GridLayoutDefinition"))
    assert grid is not None
    assert grid.findtext(report_factory._q("NumberOfColumns")) == "1"
    assert grid.findtext(report_factory._q("NumberOfRows")) == str(len(source["parameters"]))

    cells = grid.find(report_factory._q("CellDefinitions"))
    assert cells is not None
    mapped = [
        cell.findtext(report_factory._q("ParameterName"))
        for cell in cells.findall(report_factory._q("CellDefinition"))
    ]
    assert mapped == [parameter["name"] for parameter in source["parameters"]]


def test_validate_rdl_rejects_parameter_layout_missing() -> None:
    source = load_example()
    root = ET.fromstring(report_factory.generate_rdl(source))
    layout = root.find(report_factory._q("ReportParametersLayout"))
    assert layout is not None
    root.remove(layout)
    invalid_rdl = ET.tostring(root, encoding="unicode")

    with pytest.raises(report_factory.ReportSpecError, match="ReportParametersLayout"):
        report_factory.validate_rdl(invalid_rdl, source)



def test_fabric_rdl_2016_header_is_emitted_and_deterministic() -> None:
    source = load_example()
    first = report_factory.generate_rdl(source)
    second = report_factory.generate_rdl(source)
    assert first == second

    root = ET.fromstring(first)
    assert root.attrib.get("MustUnderstand") == "df"
    assert root.findtext(report_factory._rd("ReportUnitType")) == "Inch"
    report_id = root.findtext(report_factory._rd("ReportID"))
    assert report_id is not None
    assert str(uuid.UUID(report_id)) == report_id
    assert root.findtext(report_factory._df("DefaultFontFamily")) == "Segoe UI"
    assert root.findtext(report_factory._q("AutoRefresh")) == "0"

    children = list(root)
    section_index = next(i for i, node in enumerate(children) if node.tag == report_factory._q("ReportSections"))
    layout_index = next(i for i, node in enumerate(children) if node.tag == report_factory._q("ReportParametersLayout"))
    assert layout_index > section_index


def test_validate_rdl_rejects_missing_fabric_header() -> None:
    source = load_example()
    root = ET.fromstring(report_factory.generate_rdl(source))
    root.attrib.pop("MustUnderstand", None)
    invalid_rdl = ET.tostring(root, encoding="unicode")

    with pytest.raises(report_factory.ReportSpecError, match="MustUnderstand"):
        report_factory.validate_rdl(invalid_rdl, source)
