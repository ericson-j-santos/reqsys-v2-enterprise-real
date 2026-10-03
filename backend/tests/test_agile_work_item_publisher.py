import pytest

from app.services.agile_work_item_publisher import (
    AgilePublishRequest,
    SUPPORTED_AGILE_PUBLISHERS,
    build_idempotency_key,
    get_agile_publisher,
)


def _package() -> dict:
    return {
        'package_id': 'agile-123',
        'correlation_id': 'corr-publisher-001',
        'project': {
            'title': 'Planejar sprint integrada',
            'priority': 'alta',
        },
        'scrum': {
            'epic': 'Planejar sprint integrada',
            'user_story': 'Como Product Owner, quero publicar a história no backlog.',
            'acceptance_criteria': ['Critério auditável'],
            'story_points_suggested': 5,
        },
    }


@pytest.mark.parametrize('provider', SUPPORTED_AGILE_PUBLISHERS)
def test_publishers_suportados_geram_dry_run(provider):
    package = _package()
    request = AgilePublishRequest(
        package_id=package['package_id'],
        provider=provider,
        correlation_id=package['correlation_id'],
    )

    result = get_agile_publisher(provider).publish(package, request)

    assert result['provider'] == provider
    assert result['mode'] == 'dry_run'
    assert result['executed'] is False
    assert result['external_reference'] is None
    assert result['work_item']['title'] == 'Planejar sprint integrada'
    assert provider in result['work_item']['labels']


def test_idempotency_key_e_estavel_por_pacote_e_provider():
    first = build_idempotency_key('agile-123', 'gitlab')
    second = build_idempotency_key('agile-123', 'gitlab')
    different_provider = build_idempotency_key('agile-123', 'jira')

    assert first == second
    assert first != different_provider
    assert len(first) == 64


def test_publisher_rejeita_provider_nao_suportado():
    with pytest.raises(ValueError, match='unsupported_agile_publisher'):
        get_agile_publisher('provider_inexistente')


def test_publisher_rejeita_request_de_outro_provider():
    publisher = get_agile_publisher('gitlab')
    request = AgilePublishRequest(package_id='agile-123', provider='jira')

    with pytest.raises(ValueError, match='publisher_provider_mismatch'):
        publisher.publish(_package(), request)
