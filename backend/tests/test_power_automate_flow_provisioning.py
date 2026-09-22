import os

os.environ.setdefault('APP_ENV', 'test')
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test_reqsys_power_automate_flow_provisioning.db')
os.environ.setdefault('JWT_SECRET', 'reqsys-test-secret-with-minimum-safe-length')

from app.services.power_automate_provisioning import gerar_manifesto_provisionamento_flow


def test_gerar_manifesto_power_automate_flow_provisioning_p0():
    manifesto = gerar_manifesto_provisionamento_flow(
        display_name='ReqSys - Receber Requisito via HTTP',
        trigger_type='HttpRequest',
        description='Flow de pratica para ReqSys',
        target_environment='dev',
        solution_name='ReqSysAutomacao',
        correlation_id='test-flow-provisioning-001',
        dry_run=True,
    )

    assert manifesto['schema_version'] == '1.0.0'
    assert manifesto['capability'] == 'Power Automate Flow Provisioning P0'
    assert manifesto['status'] == 'planned'
    assert manifesto['correlation_id'] == 'test-flow-provisioning-001'
    assert manifesto['target']['alm_repository'] == 'ericson-j-santos/reqsys-powerplatform-alm'
    assert manifesto['target']['workflow_file'] == 'power-automate-flow-provisioning-p0.yml'
    assert manifesto['flow']['display_name'] == 'ReqSys - Receber Requisito via HTTP'
    assert manifesto['flow']['trigger_type'] == 'HttpRequest'
    assert manifesto['governance']['mode'] == 'solution_import_via_pac_cli'
    assert manifesto['governance']['requires_human_or_pipeline_approval'] is True


def test_manifesto_rejeita_trigger_invalido():
    try:
        gerar_manifesto_provisionamento_flow(
            display_name='ReqSys - Flow Invalido',
            trigger_type='WebhookMagico',
        )
    except ValueError as exc:
        assert 'TriggerType invalido' in str(exc)
    else:
        raise AssertionError('Trigger invalido deveria gerar ValueError')
