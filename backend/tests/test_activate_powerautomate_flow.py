from scripts.activate_powerautomate_flow import FlowState, _escape_odata, activate_flow


def test_escape_odata_dobra_apostrofo():
    assert _escape_odata("robo'envia") == "robo''envia"


def test_activate_flow_e_idempotente_quando_ja_ativo(monkeypatch):
    flow = FlowState(
        workflow_id='00000000-0000-0000-0000-000000000001',
        name='robo_envia_teamsv2',
        statecode=1,
        statuscode=2,
    )

    def unexpected_request(*args, **kwargs):
        raise AssertionError('Não deve chamar Dataverse para um flow já ativo.')

    monkeypatch.setattr('scripts.activate_powerautomate_flow._request_json', unexpected_request)

    assert activate_flow(environment_url='https://example.crm.dynamics.com', token='token', flow=flow) == flow


def test_activate_flow_publica_estado_ativo(monkeypatch):
    flow = FlowState(
        workflow_id='00000000-0000-0000-0000-000000000001',
        name='robo_envia_teamsv2',
        statecode=0,
        statuscode=1,
    )
    calls = []

    def fake_request(url, *, method='GET', headers=None, data=None):
        calls.append({'url': url, 'method': method, 'headers': headers, 'data': data})
        return {}

    def fake_find(**kwargs):
        return FlowState(
            workflow_id=flow.workflow_id,
            name=flow.name,
            statecode=1,
            statuscode=2,
        )

    monkeypatch.setattr('scripts.activate_powerautomate_flow._request_json', fake_request)
    monkeypatch.setattr('scripts.activate_powerautomate_flow.find_flow', fake_find)

    result = activate_flow(environment_url='https://example.crm.dynamics.com', token='token', flow=flow)

    assert result.statecode == 1
    assert calls[0]['method'] == 'PATCH'
    assert calls[0]['data'] == {'statecode': 1, 'statuscode': 2}
    assert calls[0]['headers']['If-Match'] == '*'
