import pytest

from app.services.requisito_classifier import (
    avaliar_classificador,
    classificar_requisito,
)


@pytest.mark.parametrize(
    ('texto', 'categoria'),
    [
        ('O sistema deve permitir cadastrar uma nova demanda.', 'FUNCIONAL'),
        ('A API deve responder com latência inferior a 500 ms.', 'NAO_FUNCIONAL'),
        ('O acesso deve exigir autenticação MFA e auditoria.', 'SEGURANCA'),
        ('Integrar com API REST externa por endpoint.', 'INTEGRACAO'),
        ('Persistir os dados em tabela SQL e disponibilizar relatório.', 'DADOS'),
        ('A tela deve ser responsiva e acessível ao usuário.', 'UX'),
        ('O deploy deve possuir rollback, health check e monitoramento.', 'OPERACIONAL'),
    ],
)
def test_classificador_identifica_categoria(texto, categoria):
    resultado = classificar_requisito(texto)
    assert resultado.categoria == categoria
    assert resultado.confianca > 0
    assert resultado.baseline == 'keyword-weighted-v1'


def test_sinal_especifico_supera_verbo_funcional_generico():
    resultado = classificar_requisito('A API deve responder com latência inferior a 500 ms.')
    assert resultado.categoria == 'NAO_FUNCIONAL'
    assert resultado.scores['NAO_FUNCIONAL'] > resultado.scores['FUNCIONAL']
    assert 'latência' in resultado.evidencias


def test_classificador_rejeita_texto_vazio():
    with pytest.raises(ValueError, match='obrigatório'):
        classificar_requisito('   ')


def test_avaliacao_calcula_metricas_perfeitas():
    y_true = ['FUNCIONAL', 'SEGURANCA', 'INTEGRACAO', 'DADOS']
    y_pred = ['FUNCIONAL', 'SEGURANCA', 'INTEGRACAO', 'DADOS']
    metricas = avaliar_classificador(y_true, y_pred)
    assert metricas.acuracia == 1.0
    assert metricas.macro_precision == 1.0
    assert metricas.macro_recall == 1.0
    assert metricas.macro_f1 == 1.0
    assert metricas.matriz_confusao['SEGURANCA']['SEGURANCA'] == 1


def test_avaliacao_evidencia_erro_na_matriz_confusao():
    y_true = ['FUNCIONAL', 'SEGURANCA', 'SEGURANCA', 'INTEGRACAO']
    y_pred = ['FUNCIONAL', 'FUNCIONAL', 'SEGURANCA', 'INTEGRACAO']
    metricas = avaliar_classificador(y_true, y_pred)
    assert metricas.acuracia == 0.75
    assert metricas.matriz_confusao['SEGURANCA']['FUNCIONAL'] == 1
    assert metricas.suporte['SEGURANCA'] == 2
    assert 0 < metricas.macro_f1 < 1


def test_avaliacao_rejeita_tamanhos_diferentes():
    with pytest.raises(ValueError, match='mesmo tamanho'):
        avaliar_classificador(['FUNCIONAL'], [])


def test_avaliacao_rejeita_categoria_desconhecida():
    with pytest.raises(ValueError, match='categorias desconhecidas'):
        avaliar_classificador(['OUTRA'], ['OUTRA'])
