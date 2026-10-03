from __future__ import annotations

import base64
import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from app.schemas.paginated_report import (
    PaginatedReportField,
    PaginatedReportGenerateRequest,
    PaginatedReportParameter,
)

RDL_NS = 'http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition'
RD_NS = 'http://schemas.microsoft.com/SQLServer/reporting/reportdesigner'
FACTORY_VERSION = '0.1.0'
DATASET_NAME = 'DataSet1'

ET.register_namespace('', RDL_NS)
ET.register_namespace('rd', RD_NS)


def _q(tag: str) -> str:
    return f'{{{RDL_NS}}}{tag}'


def _rd(tag: str) -> str:
    return f'{{{RD_NS}}}{tag}'


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(parent: ET.Element, tag: str, value: str) -> ET.Element:
    element = ET.SubElement(parent, _q(tag))
    element.text = value
    return element


def _stable_fingerprint(request: PaginatedReportGenerateRequest) -> str:
    canonical = json.dumps(
        request.model_dump(mode='json'),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


def _dotnet_type(field: PaginatedReportField) -> str:
    return {
        'String': 'System.String',
        'Integer': 'System.Int32',
        'Float': 'System.Double',
        'Decimal': 'System.Decimal',
        'DateTime': 'System.DateTime',
        'Boolean': 'System.Boolean',
    }[field.data_type]


def _parameter_rdl_type(parameter: PaginatedReportParameter) -> str:
    if parameter.data_type == 'Decimal':
        return 'Float'
    return parameter.data_type


def _style_border(parent: ET.Element, *, background: str | None = None, bold: bool = False) -> None:
    style = ET.SubElement(parent, _q('Style'))
    border = ET.SubElement(style, _q('Border'))
    _text(border, 'Style', 'Solid')
    _text(border, 'Color', '#D0D7DE')
    _text(style, 'PaddingLeft', '4pt')
    _text(style, 'PaddingRight', '4pt')
    _text(style, 'PaddingTop', '3pt')
    _text(style, 'PaddingBottom', '3pt')
    if background:
        _text(style, 'BackgroundColor', background)
    if bold:
        _text(style, 'FontWeight', 'Bold')


def _textbox(name: str, value: str, *, header: bool = False) -> ET.Element:
    textbox = ET.Element(_q('Textbox'), {'Name': name})
    _text(textbox, 'CanGrow', 'true')
    _text(textbox, 'KeepTogether', 'true')
    paragraphs = ET.SubElement(textbox, _q('Paragraphs'))
    paragraph = ET.SubElement(paragraphs, _q('Paragraph'))
    text_runs = ET.SubElement(paragraph, _q('TextRuns'))
    text_run = ET.SubElement(text_runs, _q('TextRun'))
    _text(text_run, 'Value', value)
    text_style = ET.SubElement(text_run, _q('Style'))
    if header:
        _text(text_style, 'FontWeight', 'Bold')
    ET.SubElement(paragraph, _q('Style'))
    _style_border(textbox, background='#F6F8FA' if header else None, bold=header)
    return textbox


def _append_data_sources(root: ET.Element, request: PaginatedReportGenerateRequest, fingerprint: str) -> None:
    data_sources = ET.SubElement(root, _q('DataSources'))
    data_source = ET.SubElement(data_sources, _q('DataSource'), {'Name': request.data_source_name})
    connection = ET.SubElement(data_source, _q('ConnectionProperties'))
    _text(connection, 'DataProvider', 'SQL')
    _text(connection, 'ConnectString', request.connection_string_template)
    _text(connection, 'IntegratedSecurity', 'false')
    data_source_id = uuid.uuid5(uuid.NAMESPACE_URL, f'reqsys:paginated-report:datasource:{fingerprint}')
    rd_id = ET.SubElement(data_source, _rd('DataSourceID'))
    rd_id.text = str(data_source_id)


def _append_dataset(root: ET.Element, request: PaginatedReportGenerateRequest) -> None:
    data_sets = ET.SubElement(root, _q('DataSets'))
    data_set = ET.SubElement(data_sets, _q('DataSet'), {'Name': DATASET_NAME})

    query = ET.SubElement(data_set, _q('Query'))
    _text(query, 'DataSourceName', request.data_source_name)
    if request.parameters:
        query_parameters = ET.SubElement(query, _q('QueryParameters'))
        for parameter in request.parameters:
            query_parameter = ET.SubElement(
                query_parameters,
                _q('QueryParameter'),
                {'Name': f'@{parameter.name}'},
            )
            _text(query_parameter, 'Value', f'=Parameters!{parameter.name}.Value')
    _text(query, 'CommandText', request.query)

    fields = ET.SubElement(data_set, _q('Fields'))
    for field in request.fields:
        field_element = ET.SubElement(fields, _q('Field'), {'Name': field.name})
        _text(field_element, 'DataField', field.name)
        type_name = ET.SubElement(field_element, _rd('TypeName'))
        type_name.text = _dotnet_type(field)


def _append_parameters(root: ET.Element, request: PaginatedReportGenerateRequest) -> None:
    if not request.parameters:
        return
    parameters = ET.SubElement(root, _q('ReportParameters'))
    for parameter in request.parameters:
        element = ET.SubElement(parameters, _q('ReportParameter'), {'Name': parameter.name})
        _text(element, 'DataType', _parameter_rdl_type(parameter))
        _text(element, 'Nullable', str(parameter.nullable).lower())
        _text(element, 'AllowBlank', str(parameter.allow_blank).lower())
        if parameter.default_value is not None:
            default_value = ET.SubElement(element, _q('DefaultValue'))
            values = ET.SubElement(default_value, _q('Values'))
            _text(values, 'Value', parameter.default_value)
        _text(element, 'Prompt', parameter.prompt or parameter.name)


def _append_title(report_items: ET.Element, request: PaginatedReportGenerateRequest) -> None:
    title = _textbox('ReportTitle', request.display_name, header=True)
    _text(title, 'Top', '0in')
    _text(title, 'Left', '0in')
    _text(title, 'Height', '0.45in')
    _text(title, 'Width', '10in' if request.page_orientation == 'landscape' else '6.5in')
    report_items.append(title)


def _append_tablix(report_items: ET.Element, request: PaginatedReportGenerateRequest) -> None:
    column_width = 1.5
    total_width = column_width * len(request.fields)

    tablix = ET.SubElement(report_items, _q('Tablix'), {'Name': 'DetailTable'})
    body = ET.SubElement(tablix, _q('TablixBody'))

    columns = ET.SubElement(body, _q('TablixColumns'))
    for _ in request.fields:
        column = ET.SubElement(columns, _q('TablixColumn'))
        _text(column, 'Width', f'{column_width:.2f}in')

    rows = ET.SubElement(body, _q('TablixRows'))

    header_row = ET.SubElement(rows, _q('TablixRow'))
    _text(header_row, 'Height', '0.30in')
    header_cells = ET.SubElement(header_row, _q('TablixCells'))
    for index, field in enumerate(request.fields):
        cell = ET.SubElement(header_cells, _q('TablixCell'))
        contents = ET.SubElement(cell, _q('CellContents'))
        contents.append(_textbox(f'Header_{index}_{field.name}', field.title or field.name, header=True))

    detail_row = ET.SubElement(rows, _q('TablixRow'))
    _text(detail_row, 'Height', '0.26in')
    detail_cells = ET.SubElement(detail_row, _q('TablixCells'))
    for index, field in enumerate(request.fields):
        cell = ET.SubElement(detail_cells, _q('TablixCell'))
        contents = ET.SubElement(cell, _q('CellContents'))
        contents.append(_textbox(f'Detail_{index}_{field.name}', f'=Fields!{field.name}.Value'))

    column_hierarchy = ET.SubElement(tablix, _q('TablixColumnHierarchy'))
    column_members = ET.SubElement(column_hierarchy, _q('TablixMembers'))
    for _ in request.fields:
        ET.SubElement(column_members, _q('TablixMember'))

    row_hierarchy = ET.SubElement(tablix, _q('TablixRowHierarchy'))
    row_members = ET.SubElement(row_hierarchy, _q('TablixMembers'))
    header_member = ET.SubElement(row_members, _q('TablixMember'))
    _text(header_member, 'KeepWithGroup', 'After')
    detail_member = ET.SubElement(row_members, _q('TablixMember'))
    ET.SubElement(detail_member, _q('Group'), {'Name': 'Details'})

    _text(tablix, 'DataSetName', DATASET_NAME)
    _text(tablix, 'Top', '0.65in')
    _text(tablix, 'Left', '0in')
    _text(tablix, 'Height', '0.56in')
    _text(tablix, 'Width', f'{total_width:.2f}in')
    ET.SubElement(tablix, _q('Style'))


def _append_sections(root: ET.Element, request: PaginatedReportGenerateRequest) -> None:
    sections = ET.SubElement(root, _q('ReportSections'))
    section = ET.SubElement(sections, _q('ReportSection'))

    body = ET.SubElement(section, _q('Body'))
    report_items = ET.SubElement(body, _q('ReportItems'))
    _append_title(report_items, request)
    _append_tablix(report_items, request)
    _text(body, 'Height', '2in')
    ET.SubElement(body, _q('Style'))

    content_width = max(6.5, min(10.0, len(request.fields) * 1.5))
    _text(section, 'Width', f'{content_width:.2f}in')

    page = ET.SubElement(section, _q('Page'))
    if request.page_orientation == 'landscape':
        _text(page, 'PageHeight', '8.27in')
        _text(page, 'PageWidth', '11.69in')
    else:
        _text(page, 'PageHeight', '11.69in')
        _text(page, 'PageWidth', '8.27in')
    _text(page, 'LeftMargin', '0.5in')
    _text(page, 'RightMargin', '0.5in')
    _text(page, 'TopMargin', '0.5in')
    _text(page, 'BottomMargin', '0.5in')
    ET.SubElement(page, _q('Style'))


def _append_parameter_layout(root: ET.Element, request: PaginatedReportGenerateRequest) -> None:
    layout = ET.SubElement(root, _q('ReportParametersLayout'))
    grid = ET.SubElement(layout, _q('GridLayoutDefinition'))
    columns = 4
    rows = max(1, math.ceil(len(request.parameters) / columns))
    _text(grid, 'NumberOfColumns', str(columns))
    _text(grid, 'NumberOfRows', str(rows))


def gerar_paginated_report(request: PaginatedReportGenerateRequest) -> dict:
    fingerprint = _stable_fingerprint(request)
    report_id = uuid.uuid5(uuid.NAMESPACE_URL, f'reqsys:paginated-report:{fingerprint}')

    root = ET.Element(_q('Report'))
    report_unit = ET.SubElement(root, _rd('ReportUnitType'))
    report_unit.text = 'Inch'
    report_id_element = ET.SubElement(root, _rd('ReportID'))
    report_id_element.text = str(report_id)
    _text(root, 'Description', request.description)
    _text(root, 'AutoRefresh', '0')
    _append_data_sources(root, request, fingerprint)
    _append_dataset(root, request)
    _append_parameters(root, request)
    _append_sections(root, request)
    _append_parameter_layout(root, request)

    ET.indent(root, space='  ')
    rdl_xml = ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
    rdl_bytes = rdl_xml.encode('utf-8')
    rdl_base64 = base64.b64encode(rdl_bytes).decode('ascii')
    definition_sha256 = hashlib.sha256(rdl_bytes).hexdigest()

    definition = {
        'format': 'PaginatedReportDefinition',
        'parts': [
            {
                'path': f'{request.report_name}.rdl',
                'payload': rdl_base64,
                'payloadType': 'InlineBase64',
            }
        ],
    }

    return {
        'schema_version': FACTORY_VERSION,
        'capability': 'ReqSys Report Builder Factory P0',
        'status': 'planned' if request.dry_run else 'ready_for_publish_request',
        'correlation_id': str(uuid.uuid4()),
        'generated_at': _utc_now(),
        'definition_sha256': definition_sha256,
        'rdl_schema': RDL_NS,
        'report_name': request.report_name,
        'display_name': request.display_name,
        'target_environment': request.target_environment,
        'data_source_name': request.data_source_name,
        'dataset_name': DATASET_NAME,
        'field_count': len(request.fields),
        'parameter_count': len(request.parameters),
        'governance': {
            'mode': 'dry_run_definition' if request.dry_run else 'publish_request_not_executed',
            'external_write_performed': False,
            'inline_secret_allowed': False,
            'read_only_query_required': True,
            'publish_requires_separate_authorization': True,
        },
        'rdl_xml': rdl_xml,
        'rdl_base64': rdl_base64,
        'fabric_definition': definition,
        'fabric_create_request': {
            'displayName': request.report_name,
            'description': request.description,
            'definition': definition,
        },
    }
