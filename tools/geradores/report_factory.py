from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

RDL_NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RD_NS = "http://schemas.microsoft.com/SQLServer/reporting/reportdesigner"
DF_NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition/defaultfontfamily"
ET.register_namespace("", RDL_NS)
ET.register_namespace("rd", RD_NS)
ET.register_namespace("df", DF_NS)

FABRIC_BASE_URL = "https://api.fabric.microsoft.com/v1"
SECRET_PATTERNS = (
    re.compile(r"(?i)(?:password|pwd)\s*="),
    re.compile(r"(?i)(?:user\s*id|uid)\s*="),
    re.compile(r"(?i)(?:access[_ -]?token|client[_ -]?secret)\s*="),
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ReportSpecError(ValueError):
    """Raised when a report specification violates the deterministic contract."""


class FabricApiError(RuntimeError):
    """Raised when Fabric rejects a request or an LRO fails."""


def _q(tag: str) -> str:
    return f"{{{RDL_NS}}}{tag}"


def _rd(tag: str) -> str:
    return f"{{{RD_NS}}}{tag}"


def _df(tag: str) -> str:
    return f"{{{DF_NS}}}{tag}"


def _add(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    node = ET.SubElement(parent, _q(tag), attrs)
    if text is not None:
        node.text = str(text)
    return node


def _require_identifier(value: Any, label: str) -> str:
    text = str(value or "")
    if not IDENTIFIER_RE.fullmatch(text):
        raise ReportSpecError(f"{label} inválido: {text!r}")
    return text


def _require_nonempty(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ReportSpecError(f"{label} é obrigatório")
    return text


def load_spec(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ReportSpecError(
                "YAML requer PyYAML; use JSON ou instale PyYAML no ambiente de geração"
            ) from exc
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        raise ReportSpecError("especificação deve usar .json, .yaml ou .yml")
    if not isinstance(data, dict):
        raise ReportSpecError("a raiz da especificação deve ser um objeto")
    return data


def validate_spec(spec: dict[str, Any]) -> None:
    if spec.get("schema_version") != "1.0.0":
        raise ReportSpecError("schema_version suportado: 1.0.0")

    report = spec.get("report")
    datasource = spec.get("datasource")
    datasets = spec.get("datasets")
    components = spec.get("components")

    if not isinstance(report, dict):
        raise ReportSpecError("report deve ser um objeto")
    if not isinstance(datasource, dict):
        raise ReportSpecError("datasource deve ser um objeto")
    if not isinstance(datasets, list) or not datasets:
        raise ReportSpecError("datasets deve conter ao menos um item")
    if not isinstance(components, list) or not components:
        raise ReportSpecError("components deve conter ao menos um item")

    report_name = _require_nonempty(report.get("name"), "report.name")
    if "/" in report_name or "\\" in report_name or report_name.endswith(".rdl"):
        raise ReportSpecError("report.name deve ser um nome de item, sem caminho ou extensão .rdl")

    _require_identifier(datasource.get("name"), "datasource.name")
    provider = _require_nonempty(datasource.get("provider"), "datasource.provider")
    if provider.upper() != "SQL":
        raise ReportSpecError("MVP suporta apenas datasource.provider=SQL")
    connect_string = _require_nonempty(datasource.get("connect_string"), "datasource.connect_string")
    for pattern in SECRET_PATTERNS:
        if pattern.search(connect_string):
            raise ReportSpecError("datasource.connect_string não pode conter credenciais ou segredos")
    if datasource.get("integrated_security") is not True:
        raise ReportSpecError("MVP exige datasource.integrated_security=true")

    parameters = spec.get("parameters", [])
    if not isinstance(parameters, list):
        raise ReportSpecError("parameters deve ser uma lista")
    parameter_names: set[str] = set()
    for parameter in parameters:
        if not isinstance(parameter, dict):
            raise ReportSpecError("cada parâmetro deve ser um objeto")
        name = _require_identifier(parameter.get("name"), "parameter.name")
        if name in parameter_names:
            raise ReportSpecError(f"parâmetro duplicado: {name}")
        parameter_names.add(name)
        data_type = parameter.get("data_type", "String")
        if data_type not in {"String", "Integer", "Float", "Boolean", "DateTime"}:
            raise ReportSpecError(f"tipo de parâmetro não suportado: {data_type}")

    dataset_names: set[str] = set()
    dataset_fields: dict[str, set[str]] = {}
    for dataset in datasets:
        if not isinstance(dataset, dict):
            raise ReportSpecError("cada dataset deve ser um objeto")
        name = _require_identifier(dataset.get("name"), "dataset.name")
        if name in dataset_names:
            raise ReportSpecError(f"dataset duplicado: {name}")
        dataset_names.add(name)
        _require_nonempty(dataset.get("query"), f"dataset {name}.query")
        fields = dataset.get("fields")
        if not isinstance(fields, list) or not fields:
            raise ReportSpecError(f"dataset {name} deve declarar fields")
        names: set[str] = set()
        for field in fields:
            if not isinstance(field, dict):
                raise ReportSpecError(f"dataset {name}: field inválido")
            field_name = _require_identifier(field.get("name"), f"dataset {name}.field.name")
            if field_name in names:
                raise ReportSpecError(f"dataset {name}: field duplicado {field_name}")
            names.add(field_name)
            _require_nonempty(field.get("data_field", field_name), f"dataset {name}.{field_name}.data_field")
        dataset_fields[name] = names
        query_parameters = dataset.get("parameters", {})
        if not isinstance(query_parameters, dict):
            raise ReportSpecError(f"dataset {name}.parameters deve ser objeto")
        for query_name, expression in query_parameters.items():
            if not str(query_name).startswith("@"):
                raise ReportSpecError(f"dataset {name}: parâmetro SQL deve iniciar com @")
            expression = _require_nonempty(expression, f"dataset {name}.parameters[{query_name}]")
            match = re.fullmatch(r"=Parameters!([A-Za-z_][A-Za-z0-9_]*)\.Value", expression)
            if not match or match.group(1) not in parameter_names:
                raise ReportSpecError(
                    f"dataset {name}: expressão {expression!r} deve referenciar parâmetro declarado"
                )

    component_names: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            raise ReportSpecError("cada componente deve ser um objeto")
        if component.get("type") != "table":
            raise ReportSpecError("MVP suporta apenas component.type=table")
        name = _require_identifier(component.get("name"), "component.name")
        if name in component_names:
            raise ReportSpecError(f"componente duplicado: {name}")
        component_names.add(name)
        dataset_name = _require_identifier(component.get("dataset"), f"component {name}.dataset")
        if dataset_name not in dataset_names:
            raise ReportSpecError(f"component {name}: dataset inexistente {dataset_name}")
        columns = component.get("columns")
        if not isinstance(columns, list) or not columns:
            raise ReportSpecError(f"component {name}: columns deve conter ao menos um item")
        for column in columns:
            if not isinstance(column, dict):
                raise ReportSpecError(f"component {name}: coluna inválida")
            field_name = _require_identifier(column.get("field"), f"component {name}.column.field")
            if field_name not in dataset_fields[dataset_name]:
                raise ReportSpecError(f"component {name}: field inexistente {field_name}")
            _require_nonempty(column.get("title", field_name), f"component {name}.{field_name}.title")
            width = _require_nonempty(column.get("width", "2in"), f"component {name}.{field_name}.width")
            if not re.fullmatch(r"\d+(?:\.\d+)?(?:in|cm|mm|pt)", width):
                raise ReportSpecError(f"component {name}: width inválido {width!r}")


def _textbox(name: str, value: str, *, bold: bool = False) -> ET.Element:
    box = ET.Element(_q("Textbox"), {"Name": name})
    _add(box, "CanGrow", "true")
    paragraphs = _add(box, "Paragraphs")
    paragraph = _add(paragraphs, "Paragraph")
    runs = _add(paragraph, "TextRuns")
    run = _add(runs, "TextRun")
    _add(run, "Value", value)
    if bold:
        style = _add(run, "Style")
        _add(style, "FontWeight", "Bold")
    _add(paragraph, "Style")
    _add(box, "Style")
    return box


def _tablix(component: dict[str, Any]) -> ET.Element:
    name = component["name"]
    dataset = component["dataset"]
    columns = component["columns"]
    tablix = ET.Element(_q("Tablix"), {"Name": name})
    body = _add(tablix, "TablixBody")
    tcols = _add(body, "TablixColumns")
    for column in columns:
        tcol = _add(tcols, "TablixColumn")
        _add(tcol, "Width", column.get("width", "2in"))

    rows = _add(body, "TablixRows")
    header = _add(rows, "TablixRow")
    _add(header, "Height", "0.28in")
    header_cells = _add(header, "TablixCells")
    for index, column in enumerate(columns):
        cell = _add(header_cells, "TablixCell")
        contents = _add(cell, "CellContents")
        contents.append(_textbox(f"{name}_Header_{index}", column.get("title", column["field"]), bold=True))

    detail = _add(rows, "TablixRow")
    _add(detail, "Height", "0.24in")
    detail_cells = _add(detail, "TablixCells")
    for index, column in enumerate(columns):
        cell = _add(detail_cells, "TablixCell")
        contents = _add(cell, "CellContents")
        contents.append(_textbox(f"{name}_Detail_{index}", f'=Fields!{column["field"]}.Value'))

    column_hierarchy = _add(tablix, "TablixColumnHierarchy")
    members = _add(column_hierarchy, "TablixMembers")
    for _ in columns:
        _add(members, "TablixMember")

    row_hierarchy = _add(tablix, "TablixRowHierarchy")
    row_members = _add(row_hierarchy, "TablixMembers")
    _add(row_members, "TablixMember")
    detail_member = _add(row_members, "TablixMember")
    _add(detail_member, "Group", Name=f"{name}_Details")
    _add(tablix, "DataSetName", dataset)
    _add(tablix, "Top", "0.5in")
    _add(tablix, "Left", "0in")
    _add(tablix, "Height", "0.52in")
    total_width = sum(float(re.match(r"\d+(?:\.\d+)?", c.get("width", "2in")).group(0)) for c in columns)
    _add(tablix, "Width", f"{total_width:g}in")
    _add(tablix, "Style")
    return tablix


def generate_rdl(spec: dict[str, Any]) -> str:
    validate_spec(spec)
    report_cfg = spec["report"]
    datasource = spec["datasource"]

    report_id = uuid.uuid5(uuid.NAMESPACE_URL, f"reqsys:report-factory:{report_cfg['name']}")
    root = ET.Element(_q("Report"), {"MustUnderstand": "df"})

    report_unit_type = ET.SubElement(root, _rd("ReportUnitType"))
    report_unit_type.text = "Inch"
    report_id_node = ET.SubElement(root, _rd("ReportID"))
    report_id_node.text = str(report_id)
    default_font = ET.SubElement(root, _df("DefaultFontFamily"))
    default_font.text = "Segoe UI"
    _add(root, "AutoRefresh", "0")

    data_sources = _add(root, "DataSources")
    source = _add(data_sources, "DataSource", Name=datasource["name"])
    connection = _add(source, "ConnectionProperties")
    _add(connection, "DataProvider", datasource["provider"])
    _add(connection, "ConnectString", datasource["connect_string"])
    _add(connection, "IntegratedSecurity", "true")

    data_sets = _add(root, "DataSets")
    for dataset in spec["datasets"]:
        ds = _add(data_sets, "DataSet", Name=dataset["name"])
        query = _add(ds, "Query")
        _add(query, "DataSourceName", datasource["name"])
        _add(query, "CommandText", dataset["query"])
        if dataset.get("parameters"):
            query_parameters = _add(query, "QueryParameters")
            for sql_name, expression in dataset["parameters"].items():
                param = _add(query_parameters, "QueryParameter", Name=sql_name)
                _add(param, "Value", expression)
        fields = _add(ds, "Fields")
        for field in dataset["fields"]:
            fnode = _add(fields, "Field", Name=field["name"])
            _add(fnode, "DataField", field.get("data_field", field["name"]))
            type_node = ET.SubElement(fnode, _rd("TypeName"))
            type_node.text = field.get("type", "System.String")

    parameters = spec.get("parameters") or []
    if parameters:
        report_parameters = _add(root, "ReportParameters")
        for parameter in parameters:
            node = _add(report_parameters, "ReportParameter", Name=parameter["name"])
            _add(node, "DataType", parameter.get("data_type", "String"))
            _add(node, "Prompt", parameter.get("prompt", parameter["name"]))
            if "default" in parameter:
                default = _add(node, "DefaultValue")
                values = _add(default, "Values")
                _add(values, "Value", str(parameter["default"]))

    sections = _add(root, "ReportSections")
    section = _add(sections, "ReportSection")
    body = _add(section, "Body")
    report_items = _add(body, "ReportItems")

    title = _textbox("ReportTitle", report_cfg.get("title", report_cfg["name"]), bold=True)
    _add(title, "Top", "0in")
    _add(title, "Left", "0in")
    _add(title, "Height", "0.35in")
    _add(title, "Width", "8in")
    report_items.append(title)

    top = 0.5
    for component in spec["components"]:
        tablix = _tablix(component)
        top_node = tablix.find(_q("Top"))
        if top_node is not None:
            top_node.text = f"{top:g}in"
        report_items.append(tablix)
        top += 1.0

    _add(body, "Height", f"{max(top + 0.25, 2.0):g}in")
    _add(body, "Style")

    landscape = report_cfg.get("page", {}).get("orientation", "portrait") == "landscape"
    width, height = ("11in", "8.5in") if landscape else ("8.5in", "11in")
    page = _add(section, "Page")
    _add(page, "PageHeight", height)
    _add(page, "PageWidth", width)
    for margin in ("LeftMargin", "RightMargin", "TopMargin", "BottomMargin"):
        _add(page, margin, "0.5in")
    _add(page, "Style")
    _add(section, "Width", "10in" if landscape else "7.5in")

    if parameters:
        parameter_layout = _add(root, "ReportParametersLayout")
        grid = _add(parameter_layout, "GridLayoutDefinition")
        _add(grid, "NumberOfColumns", "1")
        _add(grid, "NumberOfRows", str(len(parameters)))
        cells = _add(grid, "CellDefinitions")
        for row_index, parameter in enumerate(parameters):
            cell = _add(cells, "CellDefinition")
            _add(cell, "ColumnIndex", "0")
            _add(cell, "RowIndex", str(row_index))
            _add(cell, "ParameterName", parameter["name"])

    ET.indent(root, space="  ")
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8") + "\n"


def validate_rdl(rdl: str, spec: dict[str, Any]) -> None:
    validate_spec(spec)
    try:
        root = ET.fromstring(rdl)
    except ET.ParseError as exc:
        raise ReportSpecError(f"RDL inválido: {exc}") from exc
    if root.tag != _q("Report"):
        raise ReportSpecError("RDL deve usar namespace Report Definition 2016")
    if root.attrib.get("MustUnderstand") != "df":
        raise ReportSpecError("RDL Fabric exige MustUnderstand=df")
    if root.findtext(_rd("ReportUnitType"), default="") != "Inch":
        raise ReportSpecError("RDL Fabric exige rd:ReportUnitType=Inch")
    report_id = root.findtext(_rd("ReportID"), default="")
    try:
        uuid.UUID(report_id)
    except (ValueError, AttributeError) as exc:
        raise ReportSpecError("RDL Fabric exige rd:ReportID UUID válido") from exc
    if root.findtext(_df("DefaultFontFamily"), default="") != "Segoe UI":
        raise ReportSpecError("RDL Fabric exige df:DefaultFontFamily=Segoe UI")
    if root.findtext(_q("AutoRefresh"), default="") != "0":
        raise ReportSpecError("RDL Fabric exige AutoRefresh=0")
    lower = rdl.lower()
    for pattern in SECRET_PATTERNS:
        if pattern.search(lower):
            raise ReportSpecError("RDL contém material semelhante a credencial")
    datasets = {node.attrib.get("Name") for node in root.findall(f".//{_q('DataSet')}")}
    expected_datasets = {item["name"] for item in spec["datasets"]}
    if datasets != expected_datasets:
        raise ReportSpecError("datasets gerados divergem da especificação")
    tables = {node.attrib.get("Name") for node in root.findall(f".//{_q('Tablix')}")}
    expected_tables = {item["name"] for item in spec["components"]}
    if tables != expected_tables:
        raise ReportSpecError("componentes gerados divergem da especificação")

    expected_parameters = [item["name"] for item in spec.get("parameters", [])]
    report_parameters = root.find(_q("ReportParameters"))
    parameter_layout = root.find(_q("ReportParametersLayout"))

    if expected_parameters:
        if report_parameters is None:
            raise ReportSpecError("RDL parametrizado exige ReportParameters")
        if parameter_layout is None:
            raise ReportSpecError("RDL 2016 parametrizado exige ReportParametersLayout")

        generated_parameters = [
            str(node.attrib.get("Name") or "")
            for node in report_parameters.findall(_q("ReportParameter"))
        ]
        if generated_parameters != expected_parameters:
            raise ReportSpecError("ReportParameters divergem da especificação")

        grid = parameter_layout.find(_q("GridLayoutDefinition"))
        if grid is None:
            raise ReportSpecError("ReportParametersLayout exige GridLayoutDefinition")

        try:
            column_count = int(grid.findtext(_q("NumberOfColumns"), default="0"))
            row_count = int(grid.findtext(_q("NumberOfRows"), default="0"))
        except ValueError as exc:
            raise ReportSpecError("grid de parâmetros possui dimensão inválida") from exc
        if column_count < 1 or row_count < 1:
            raise ReportSpecError("grid de parâmetros deve possuir dimensões positivas")

        cell_definitions = grid.find(_q("CellDefinitions"))
        if cell_definitions is None:
            raise ReportSpecError("grid de parâmetros exige CellDefinitions")
        cells = cell_definitions.findall(_q("CellDefinition"))
        if len(cells) != len(expected_parameters):
            raise ReportSpecError("CellDefinitions deve mapear todos os parâmetros")

        coordinates: set[tuple[int, int]] = set()
        mapped_parameters: list[str] = []
        for cell in cells:
            try:
                column_index = int(cell.findtext(_q("ColumnIndex"), default="-1"))
                row_index = int(cell.findtext(_q("RowIndex"), default="-1"))
            except ValueError as exc:
                raise ReportSpecError("CellDefinition possui índice inválido") from exc
            parameter_name = cell.findtext(_q("ParameterName"), default="")
            coordinate = (column_index, row_index)
            if not (0 <= column_index < column_count and 0 <= row_index < row_count):
                raise ReportSpecError("CellDefinition fora dos limites do grid")
            if coordinate in coordinates:
                raise ReportSpecError("CellDefinition possui coordenada duplicada")
            coordinates.add(coordinate)
            mapped_parameters.append(parameter_name)

        if len(set(mapped_parameters)) != len(mapped_parameters):
            raise ReportSpecError("CellDefinition referencia parâmetro duplicado")
        if set(mapped_parameters) != set(expected_parameters):
            raise ReportSpecError("CellDefinitions divergem dos parâmetros da especificação")
    elif report_parameters is not None or parameter_layout is not None:
        raise ReportSpecError("RDL sem parâmetros não deve declarar layout de parâmetros")


def build_fabric_definition(display_name: str, rdl: str) -> dict[str, Any]:
    display_name = _require_nonempty(display_name, "display_name")
    if "/" in display_name or "\\" in display_name:
        raise ReportSpecError("display_name não pode conter caminho")
    payload = base64.b64encode(rdl.encode("utf-8")).decode("ascii")
    return {
        "format": "PaginatedReportDefinition",
        "parts": [
            {
                "path": f"{display_name}.rdl",
                "payload": payload,
                "payloadType": "InlineBase64",
            }
        ],
    }


def build_create_request(spec: dict[str, Any], rdl: str) -> dict[str, Any]:
    validate_rdl(rdl, spec)
    report = spec["report"]
    body = {
        "displayName": report["name"],
        "definition": build_fabric_definition(report["name"], rdl),
    }
    description = str(report.get("description") or "").strip()
    if description:
        body["description"] = description[:256]
    return body


def _request_json(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, str], Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else None
            return response.status, dict(response.headers.items()), parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise FabricApiError(f"Fabric HTTP {exc.code}: {raw[:2000]}") from exc


def _wait_lro(location: str, token: str, timeout_seconds: int = 300) -> Any:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status, headers, body = _request_json("GET", location, token)
        if status not in {200, 202}:
            raise FabricApiError(f"LRO retornou HTTP inesperado {status}")
        if status == 200:
            state = str((body or {}).get("status", "")).lower() if isinstance(body, dict) else ""
            if not state or state in {"succeeded", "completed"}:
                return body
            if state in {"failed", "cancelled", "canceled"}:
                raise FabricApiError(f"LRO terminou em {state}: {body}")
        retry_after = int(headers.get("Retry-After", "2") or "2")
        time.sleep(max(1, min(retry_after, 15)))
    raise FabricApiError(f"LRO excedeu timeout de {timeout_seconds}s")


def publish_to_fabric(
    spec: dict[str, Any],
    rdl: str,
    *,
    workspace_id: str,
    token: str,
    report_id: str | None = None,
    timeout_seconds: int = 300,
) -> Any:
    workspace_id = _require_nonempty(workspace_id, "workspace_id")
    token = _require_nonempty(token, "FABRIC_ACCESS_TOKEN")
    report = spec["report"]
    definition = build_fabric_definition(report["name"], rdl)
    if report_id:
        url = f"{FABRIC_BASE_URL}/workspaces/{workspace_id}/paginatedReports/{report_id}/updateDefinition"
        payload = {"definition": definition}
    else:
        url = f"{FABRIC_BASE_URL}/workspaces/{workspace_id}/paginatedReports"
        payload = build_create_request(spec, rdl)

    status, headers, body = _request_json("POST", url, token, payload)
    if status in {200, 201}:
        return body
    if status == 202:
        location = headers.get("Location") or headers.get("location")
        if not location:
            raise FabricApiError("Fabric retornou 202 sem Location para acompanhar a operação")
        return _wait_lro(location, token, timeout_seconds)
    raise FabricApiError(f"Fabric retornou HTTP inesperado {status}")


def _write_text(path: str | Path, content: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ReqSys Report Factory: ReportSpec -> RDL -> Fabric API")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="valida a especificação sem produzir artefato")
    validate.add_argument("--spec", required=True)

    generate = sub.add_parser("generate", help="gera RDL determinístico")
    generate.add_argument("--spec", required=True)
    generate.add_argument("--output", required=True)

    payload = sub.add_parser("fabric-payload", help="gera payload JSON compatível com Fabric")
    payload.add_argument("--spec", required=True)
    payload.add_argument("--output", required=True)

    publish = sub.add_parser("publish", help="cria ou atualiza relatório paginado no Fabric")
    publish.add_argument("--spec", required=True)
    publish.add_argument("--workspace-id", required=True)
    publish.add_argument("--report-id")
    publish.add_argument("--timeout-seconds", type=int, default=300)

    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        spec = load_spec(args.spec)
        validate_spec(spec)
        if args.command == "validate":
            print(json.dumps({"status": "passed", "report": spec["report"]["name"]}, ensure_ascii=False))
            return 0

        rdl = generate_rdl(spec)
        validate_rdl(rdl, spec)

        if args.command == "generate":
            _write_text(args.output, rdl)
            print(json.dumps({"status": "passed", "output": str(args.output)}, ensure_ascii=False))
            return 0

        if args.command == "fabric-payload":
            body = build_create_request(spec, rdl)
            _write_text(args.output, json.dumps(body, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({"status": "passed", "output": str(args.output)}, ensure_ascii=False))
            return 0

        token = os.getenv("FABRIC_ACCESS_TOKEN", "")
        result = publish_to_fabric(
            spec,
            rdl,
            workspace_id=args.workspace_id,
            token=token,
            report_id=args.report_id,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps({"status": "passed", "fabric": result}, ensure_ascii=False))
        return 0
    except (ReportSpecError, FabricApiError, OSError, json.JSONDecodeError) as exc:
        # O detalhe da exceção fica no log (stderr), correlacionado por error_id;
        # a saída estruturada carrega apenas mensagem genérica e o identificador.
        error_id = uuid.uuid4().hex[:12]
        print(f"[{error_id}] {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_id": error_id,
                    "message": "Falha ao processar a solicitação; consulte o log pelo error_id.",
                },
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
