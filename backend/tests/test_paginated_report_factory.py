import base64
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.paginated_report import PaginatedReportGenerateRequest
from app.services.paginated_report_factory import RDL_NS, gerar_paginated_report


def _request(**overrides):
    values = {
        'report_name': 'DemandasPorStatus',
        'display_name': 'Demandas por Status',
        'description': 'Resumo paginado de demandas por status.',
        'target_environment': 'dev',
        'query': (
            'SELECT Status, COUNT(*) AS Quantidade '
            'FROM tbDemandas WHERE DataCriacao >= @DataInicio GROUP BY Status'
        ),
        'fields': [
            {'name': 'Status', 'title': 'Status', 'data_type': 'String'},
            {'name': 'Quantidade', 'title': 'Quantidade', 'data_type': 'Integer'},
        ],
        'parameters': [
            {
                'name': 'DataInicio',
                'prompt': 'Data inicial',
                'data_type': 'DateTime',
                'nullable': False,
            }
        ],
        'page_orientation': 'landscape',
        'dry_run': True,
    }
    values.update(overrides)
    return PaginatedReportGenerateRequest(**values)


def test_factory_gera_rdl_fabric_parseavel_e_sem_escrita_externa():
    result = gerar_paginated_report(_request())

    assert result['capability'] == 'ReqSys Report Builder Factory P0'
    assert result['status'] == 'planned'
    assert result['governance']['external_write_performed'] is False
    assert result['governance']['publish_requires_separate_authorization'] is True

    definition = result['fabric_create_request']['definition']
    assert definition['format'] == 'PaginatedReportDefinition'
    assert definition['parts'][0]['path'] == 'DemandasPorStatus.rdl'
    assert definition['parts'][0]['payloadType'] == 'InlineBase64'

    decoded = base64.b64decode(definition['parts'][0]['payload']).decode('utf-8')
    assert decoded == result['rdl_xml']

    root = ET.fromstring(decoded)
    ns = {'r': RDL_NS}
    assert root.tag == f'{{{RDL_NS}}}Report'
    assert root.find("r:DataSources/r:DataSource[@Name='ReqSysSqlServer']", ns) is not None
    assert root.find("r:DataSets/r:DataSet[@Name='DataSet1']", ns) is not None
    assert root.find("r:ReportSections/r:ReportSection", ns) is not None
    assert root.find("r:ReportParameters/r:ReportParameter[@Name='DataInicio']", ns) is not None

    command = root.find('r:DataSets/r:DataSet/r:Query/r:CommandText', ns)
    assert command is not None
    assert '@DataInicio' in command.text

    query_parameter = root.find(
        "r:DataSets/r:DataSet/r:Query/r:QueryParameters/r:QueryParameter[@Name='@DataInicio']/r:Value",
        ns,
    )
    assert query_parameter is not None
    assert query_parameter.text == '=Parameters!DataInicio.Value'


def test_factory_e_deterministica_para_mesma_especificacao():
    request = _request()
    first = gerar_paginated_report(request)
    second = gerar_paginated_report(request)

    assert first['rdl_base64'] == second['rdl_base64']
    assert first['definition_sha256'] == second['definition_sha256']


def test_factory_rejeita_segredo_inline_na_connection_string():
    with pytest.raises(ValidationError, match='segredo inline'):
        _request(connection_string_template='Server=db;Database=reqsys;Password=nao-pode')


@pytest.mark.parametrize(
    'query',
    [
        'DELETE FROM tbDemandas',
        'UPDATE tbDemandas SET Status = 1',
        'EXEC dbo.GerarRelatorio',
        'SELECT * FROM tbDemandas; DROP TABLE tbDemandas',
    ],
)
def test_factory_rejeita_query_que_nao_e_somente_leitura(query):
    with pytest.raises(ValidationError):
        _request(query=query)


def test_endpoint_gera_payload_report_builder_sem_publicar():
    client = TestClient(app)
    response = client.post(
        '/v1/hub-lowcode/reports/paginated/generate',
        json={
            'report_name': 'DemandasPorStatus',
            'display_name': 'Demandas por Status',
            'query': 'SELECT Status, COUNT(*) AS Quantidade FROM tbDemandas GROUP BY Status',
            'fields': [
                {'name': 'Status', 'title': 'Status'},
                {'name': 'Quantidade', 'title': 'Quantidade', 'data_type': 'Integer'},
            ],
            'dry_run': True,
        },
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['report_name'] == 'DemandasPorStatus'
    assert data['fabric_definition']['format'] == 'PaginatedReportDefinition'
    assert data['governance']['external_write_performed'] is False


def test_endpoint_controle_negativo_rejeita_sql_destrutivo():
    client = TestClient(app)
    response = client.post(
        '/v1/hub-lowcode/reports/paginated/generate',
        json={
            'report_name': 'RelatorioInvalido',
            'display_name': 'Relatorio Invalido',
            'query': 'DELETE FROM tbDemandas',
            'fields': [{'name': 'Status'}],
        },
    )

    assert response.status_code == 422
