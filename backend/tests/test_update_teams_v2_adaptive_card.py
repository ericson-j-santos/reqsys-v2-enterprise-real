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


def test_apply_card_change_declara_adaptive_card_no_schema():
    after = apply_card_change(REAL_CLIENTDATA)
    schema = _analisar_json(after)['inputs']['schema']

    assert schema['properties']['adaptiveCard'] == {'type': 'object'}
    # campos existentes/obrigatórios não devem ser tocados
    assert schema['required'] == ['to', 'title', 'content', 'signature']
    assert schema['properties']['title'] == {'type': 'string'}


def test_json_to_concat_expression_preserva_aspas_e_escapa_o_valor():
    card = {'type': 'AdaptiveCard', 'title': "@{body('Analisar_JSON')?['title']}", 'fixed': 1}
    expr = _json_to_concat_expression(card)

    assert expr.startswith('concat(')
    # a expressão crua deve estar envolvida por replace(...) (escaping), não solta
    assert "replace(body('Analisar_JSON')?['title']" in expr
    # as aspas JSON ao redor do placeholder viram texto literal separado, não somem
    assert '"title": "\'' in expr or '\'"title": "\'' in expr


def test_json_to_concat_expression_bate_com_construcao_manual_dos_mesmos_blocos():
    """Trava a estrutura exata de concat() usando os MESMOS blocos internos
    (_wdl_string_literal / _wdl_escape_json_string) que a função usa — sem
    reimplementar/duplicar a lógica de escaping no teste, só recompor as
    mesmas peças na ordem esperada."""
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
    # a barra invertida precisa ser escapada no primeiro replace (mais interno),
    # senão a barra inserida ao escapar aspas seria escapada de novo por engano
    first_replace_args_index = escaped.index("body('Analisar_JSON')?['content']") + len("body('Analisar_JSON')?['content']")
    assert escaped[first_replace_args_index:].startswith(", '\\', '\\\\'")


def _simular_wdl_replace_chain(raw_value: str) -> str:
    """Reimplementação em Python puro da MESMA cadeia de replace() que
    _wdl_escape_json_string gera (barra invertida, aspas, CR, LF, nessa
    ordem), usada só para verificação determinística local sem precisar de
    um flow real do Power Automate."""
    backslash, quote = chr(92), chr(34)
    value = raw_value
    value = value.replace(backslash, backslash * 2)
    value = value.replace(quote, backslash + quote)
    value = value.replace(chr(13), '')
    value = value.replace(chr(10), backslash + 'n')
    return value


def test_build_message_body_expression_produz_json_valido_com_titulo_e_conteudo_reais():
    """Regressão: a versão anterior descartava as aspas ao redor do
    placeholder e emendava o valor bruto (sem aspas, sem escaping) no meio do
    texto JSON — produzindo JSON inválido sempre que title/content continha
    travessão, aspas, barra invertida ou quebra de linha (exatamente o
    payload real que teams-commit-notification.yml envia, confirmado
    reproduzindo o bug localmente com json.loads()). Este teste simula a
    avaliação em runtime de _wdl_escape_json_string com valores reais e
    confirma que o card inteiro fica JSON válido e preserva os valores."""
    title = 'ReqSys — novo commit'
    content = 'Novo commit em org/repo\r\nBranch: main\nAutor: "Fulano"\nBarra: C:\\path\\to\\file'

    def valor_para(expressao: str) -> str:
        if "['title']" in expressao:
            return title
        if "['content']" in expressao:
            return content
        return 'valor-dinamico'

    # Reproduz exatamente o que concat() faz em runtime: pega o MESMO texto
    # template que _json_to_concat_expression usa (json.dumps do card com
    # placeholders) e, para cada placeholder "@{...}", substitui pelo valor
    # já passado pela MESMA cadeia de escaping (_simular_wdl_replace_chain),
    # mantendo as aspas JSON ao redor como texto literal — sem reserializar
    # com json.dumps de novo (isso re-escaparia um valor já escapado).
    template_text = json.dumps(adaptive_card_body(), ensure_ascii=False)
    placeholder_re = re.compile(r'"@\{([^}]*)\}"')
    parts = []
    last_end = 0
    for match in placeholder_re.finditer(template_text):
        parts.append(template_text[last_end:match.start() + 1])  # inclui aspa de abertura
        parts.append(_simular_wdl_replace_chain(valor_para(match.group(1))))
        parts.append('"')  # aspa de fechamento
        last_end = match.end()
    parts.append(template_text[last_end:])
    runtime_string = ''.join(parts)

    parsed = json.loads(runtime_string)  # não deve lançar json.JSONDecodeError
    title_text = parsed['body'][0]['items'][0]['columns'][0]['items'][0]['text']
    content_text = parsed['body'][0]['items'][0]['columns'][0]['items'][1]['text']
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


def test_diff_summary_reporta_antes_e_depois():
    before = copy.deepcopy(REAL_CLIENTDATA)
    after = apply_card_change(before)

    summary = diff_summary(REAL_CLIENTDATA, after)

    assert summary['action'] == ACTION_NAME
    assert summary['operationId'] == 'PostCardToConversation'
    assert summary['before_message_body'] == "@outputs('Compose_Message')"
    assert summary['after_message_body'] == build_message_body_expression()
