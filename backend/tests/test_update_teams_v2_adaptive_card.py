import copy
import json
import re

import pytest

from scripts.update_teams_v2_adaptive_card import (
    ACTION_NAME,
    _json_to_concat_expression,
    _wdl_escape_json_string,
    adaptive_card_body,
    apply_card_change,
    build_message_body_expression,
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
                        'Analisar_JSON': {
                            'type': 'ParseJson',
                            'inputs': {
                                'content': "@triggerBody()",
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'to': {'type': 'string'},
                                        'title': {'type': 'string'},
                                        'content': {'type': 'string'},
                                        'signature': {'type': 'string'},
                                        'stampDate': {'type': 'string'},
                                        'correlationId': {'type': 'string'},
                                    },
                                    'required': ['to', 'title', 'content', 'signature'],
                                },
                            },
                        },
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


def _analisar_json(clientdata):
    return clientdata['properties']['definition']['actions']['Scope_TRY']['actions']['Analisar_JSON']


def test_apply_card_change_troca_apenas_message_body():
    before = copy.deepcopy(REAL_CLIENTDATA)
    after = apply_card_change(before)

    before_action = _action(REAL_CLIENTDATA)
    after_action = _action(after)

    assert before_action['inputs']['parameters']['body/messageBody'] == "@outputs('Compose_Message')"
    new_body = after_action['inputs']['parameters']['body/messageBody']
    assert new_body != before_action['inputs']['parameters']['body/messageBody']
    assert new_body == build_message_body_expression()
    assert new_body.startswith("@{if(empty(body('Analisar_JSON')?['adaptiveCard']), ")
    assert new_body.endswith("body('Analisar_JSON')?['adaptiveCard'])}")


def test_apply_card_change_declara_contrato_adaptive_no_schema():
    after = apply_card_change(REAL_CLIENTDATA)
    schema = _analisar_json(after)['inputs']['schema']

    assert schema['properties']['adaptiveCard'] == {'type': 'object'}
    assert schema['properties']['adaptiveCardJson'] == {'type': 'string'}
    assert schema['properties']['renderMode'] == {'type': 'string'}
    assert schema['properties']['eventType'] == {'type': 'string'}
    assert schema['properties']['deduplicationKey'] == {'type': 'string'}
    assert schema['properties']['suppressFallbackMessage'] == {'type': 'boolean'}
    assert schema['required'] == ['to', 'title', 'content', 'signature']
    assert schema['properties']['title'] == {'type': 'string'}


def test_template_generico_usa_largura_total_e_campos_empilhados():
    card = adaptive_card_body()
    card_json = json.dumps(card, ensure_ascii=False)

    assert card['msteams']['width'] == 'Full'
    assert card['fallbackText'] == "@{body('Analisar_JSON')?['title']}"
    assert 'FactSet' not in card_json
    assert 'ColumnSet' not in card_json
    assert 'Assinatura' in card_json
    assert 'Correlation ID' in card_json
    assert all(item.get('wrap') is True for block in card['body'] for item in block.get('items', []) if item.get('type') == 'TextBlock')


def test_json_to_concat_expression_preserva_aspas_e_escapa_o_valor():
    card = {'type': 'AdaptiveCard', 'title': "@{body('Analisar_JSON')?['title']}", 'fixed': 1}
    expr = _json_to_concat_expression(card)

    assert expr.startswith('concat(')
    assert "replace(body('Analisar_JSON')?['title']" in expr
    assert '"title": "\'' in expr or '\'"title": "\'' in expr


def test_json_to_concat_expression_bate_com_construcao_manual_dos_mesmos_blocos():
    from scripts.update_teams_v2_adaptive_card import _wdl_string_literal

    card = {'a': "@{body('Analisar_JSON')?['title']}", 'b': 1}
    expr = _json_to_concat_expression(card)

    expected = 'concat(%s, %s, %s)' % (
        _wdl_string_literal('{"a": "'),
        _wdl_escape_json_string("body('Analisar_JSON')?['title']"),
        _wdl_string_literal('", "b": 1}'),
    )
    assert expr == expected


def test_wdl_escape_json_string_ordem_correta_barra_antes_de_aspas():
    escaped = _wdl_escape_json_string("body('Analisar_JSON')?['content']")

    assert escaped.count('replace(') == 4
    first_replace_args_index = escaped.index("body('Analisar_JSON')?['content']") + len("body('Analisar_JSON')?['content']")
    assert escaped[first_replace_args_index:].startswith(", '\\', '\\\\'")


def _simular_wdl_replace_chain(raw_value: str) -> str:
    backslash, quote = chr(92), chr(34)
    value = raw_value
    value = value.replace(backslash, backslash * 2)
    value = value.replace(quote, backslash + quote)
    value = value.replace(chr(13), '')
    value = value.replace(chr(10), backslash + 'n')
    return value


def test_build_message_body_expression_produz_json_valido_com_titulo_e_conteudo_reais():
    title = 'ReqSys — novo commit'
    content = 'Novo commit em org/repo\r\nBranch: main\nAutor: "Fulano"\nBarra: C:\\path\\to\\file'

    def valor_para(expressao: str) -> str:
        if "['title']" in expressao:
            return title
        if "['content']" in expressao:
            return content
        return 'valor-dinamico'

    template_text = json.dumps(adaptive_card_body(), ensure_ascii=False)
    placeholder_re = re.compile(r'"@\{([^}]*)\}"')
    parts = []
    last_end = 0
    for match in placeholder_re.finditer(template_text):
        parts.append(template_text[last_end:match.start() + 1])
        parts.append(_simular_wdl_replace_chain(valor_para(match.group(1))))
        parts.append('"')
        last_end = match.end()
    parts.append(template_text[last_end:])
    runtime_string = ''.join(parts)

    parsed = json.loads(runtime_string)
    title_text = parsed['body'][0]['items'][0]['text']
    content_text = parsed['body'][0]['items'][1]['text']
    assert title_text == title
    assert content_text == content.replace(chr(13), '')


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


def test_diff_summary_reporta_antes_depois_e_layout():
    before = copy.deepcopy(REAL_CLIENTDATA)
    after = apply_card_change(before)

    summary = diff_summary(REAL_CLIENTDATA, after)

    assert summary['action'] == ACTION_NAME
    assert summary['operationId'] == 'PostCardToConversation'
    assert summary['before_message_body'] == "@outputs('Compose_Message')"
    assert summary['after_message_body'] == build_message_body_expression()
    assert summary['layout'] == 'full-width-stacked-mobile'
