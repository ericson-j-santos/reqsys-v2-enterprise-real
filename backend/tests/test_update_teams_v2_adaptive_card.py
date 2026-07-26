import copy
import json

import pytest

from scripts.update_teams_v2_adaptive_card import (
    ACTION_NAME,
    adaptive_card_body,
    apply_card_change,
    diff_summary,
)

REAL_CLIENTDATA = {
    'properties': {
        'connectionReferences': {
            'shared_teams': {
                'runtimeSource': 'embedded',
                'connection': {'connectionReferenceLogicalName': 'new_sharedteams_0b6e2'},
                'api': {'name': 'shared_teams'},
            }
        },
        'definition': {
            '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#',
            'actions': {
                'Compose_CorrelationId': {'type': 'Compose'},
                'Scope_TRY': {
                    'type': 'Scope',
                    'actions': {
                        'Analisar_JSON': {'type': 'ParseJson'},
                        'Compose_CorrelationId_Final': {'type': 'Compose'},
                        'Condição_': {
                            'type': 'If',
                            'actions': {
                                'Compose_StampDate': {'type': 'Compose'},
                                'Compose_Message': {'type': 'Compose'},
                                'Resposta__1': {
                                    'type': 'Response',
                                    'runAfter': {ACTION_NAME: ['Succeeded']},
                                },
                                ACTION_NAME: {
                                    'runAfter': {'Compose_Message': ['Succeeded']},
                                    'type': 'OpenApiConnection',
                                    'metadata': {'operationMetadataId': 'fixed-id-must-not-change'},
                                    'inputs': {
                                        'parameters': {
                                            'poster': 'Flow bot',
                                            'location': 'Chat with Flow bot',
                                            'body/recipient': "@toLower(trim(body('Analisar_JSON')?['to']))",
                                            'body/messageBody': "@outputs('Compose_Message')",
                                        },
                                        'host': {
                                            'apiId': '/providers/Microsoft.PowerApps/apis/shared_teams',
                                            'operationId': 'PostCardToConversation',
                                            'connectionName': 'shared_teams',
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        'templateName': None,
    },
    'schemaVersion': '1.0.0.0',
}


def _action(clientdata):
    return clientdata['properties']['definition']['actions']['Scope_TRY']['actions']['Condição_']['actions'][ACTION_NAME]


def test_apply_card_change_troca_apenas_message_body():
    before = copy.deepcopy(REAL_CLIENTDATA)
    after = apply_card_change(before)

    before_action = _action(REAL_CLIENTDATA)
    after_action = _action(after)

    assert before_action['inputs']['parameters']['body/messageBody'] == "@outputs('Compose_Message')"
    new_body = after_action['inputs']['parameters']['body/messageBody']
    assert new_body != before_action['inputs']['parameters']['body/messageBody']

    card = json.loads(new_body)
    assert card['type'] == 'AdaptiveCard'
    assert 'attachments' not in card
    assert card == adaptive_card_body()


def test_apply_card_change_preserva_grafo_de_dependencias():
    after = apply_card_change(REAL_CLIENTDATA)
    after_action = _action(after)

    assert after_action['runAfter'] == {'Compose_Message': ['Succeeded']}
    assert after_action['metadata']['operationMetadataId'] == 'fixed-id-must-not-change'
    assert after_action['inputs']['parameters']['poster'] == 'Flow bot'
    assert after_action['inputs']['parameters']['location'] == 'Chat with Flow bot'
    assert after_action['inputs']['parameters']['body/recipient'] == "@toLower(trim(body('Analisar_JSON')?['to']))"
    assert after_action['inputs']['host']['operationId'] == 'PostCardToConversation'


def test_apply_card_change_nao_muta_o_original():
    original_body = _action(REAL_CLIENTDATA)['inputs']['parameters']['body/messageBody']
    apply_card_change(REAL_CLIENTDATA)
    assert _action(REAL_CLIENTDATA)['inputs']['parameters']['body/messageBody'] == original_body


def test_apply_card_change_rejeita_operacao_inesperada():
    clientdata = copy.deepcopy(REAL_CLIENTDATA)
    _action(clientdata)['inputs']['host']['operationId'] = 'PostMessageToConversation'

    with pytest.raises(ValueError, match='PostCardToConversation'):
        apply_card_change(clientdata)


def test_adaptive_card_body_referencia_acoes_reais_do_flow():
    card_json = json.dumps(adaptive_card_body())

    assert "body('Analisar_JSON')?['title']" in card_json
    assert "outputs('Compose_StampDate')" in card_json
    assert "outputs('Compose_CorrelationId_Final')" in card_json


def test_diff_summary_reporta_antes_e_depois():
    before = copy.deepcopy(REAL_CLIENTDATA)
    after = apply_card_change(before)

    summary = diff_summary(REAL_CLIENTDATA, after)

    assert summary['action'] == ACTION_NAME
    assert summary['operationId'] == 'PostCardToConversation'
    assert summary['before_message_body'] == "@outputs('Compose_Message')"
    assert json.loads(summary['after_message_body'])['type'] == 'AdaptiveCard'
