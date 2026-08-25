import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.services.requisito_classifier import CATEGORIAS
from app.services.requisito_ml_p3 import (
    EventoClassificacaoML,
    amostras_aprovadas_para_treino,
    avaliar_holdout,
    calcular_drift,
    carregar_amostras_observadas,
    carregar_holdout,
    carregar_politica_runtime,
    classificar_runtime,
    treinar_modelo_runtime,
    validar_holdout_imutavel,
)

BACKEND = Path(__file__).resolve().parents[1]
DATASET_P2 = BACKEND / 'data/ml/requisitos_classificador_v1.jsonl'
HOLDOUT = BACKEND / 'data/ml/requisitos_holdout_p3_v1.jsonl'
OBSERVADOS = BACKEND / 'data/ml/requisitos_observados_p3_v1.jsonl'
POLITICA = BACKEND / 'data/ml/politica_runtime_requisitos_p3_v1.json'


def _escrever_jsonl(caminho: Path, itens: list[dict]) -> Path:
    caminho.write_text(
        ''.join(json.dumps(item, ensure_ascii=False) + '\n' for item in itens),
        encoding='utf-8',
    )
    return caminho


def _politica_mutada(tmp_path: Path, **alteracoes) -> Path:
    item = json.loads(POLITICA.read_text(encoding='utf-8'))
    item.update(alteracoes)
    caminho = tmp_path / 'politica.json'
    caminho.write_text(json.dumps(item, ensure_ascii=False), encoding='utf-8')
    return caminho


def _holdout_item(**alteracoes) -> dict:
    item = {
        'id': 'holdout-1',
        'texto': 'O sistema deve permitir consultar uma demanda.',
        'categoria': 'FUNCIONAL',
        'origem': 'teste',
        'dataset_versao': 'requisitos-holdout-p3-v1',
    }
    item.update(alteracoes)
    return item


def _observado_item(**alteracoes) -> dict:
    item = {
        'id': 'obs-1',
        'texto': 'A tela deve exibir o status da demanda.',
        'source_ref': 'issue-anonimizada',
        'categoria_sugerida': 'UX',
        'anonimizado': True,
        'revisao_status': 'PENDENTE_HUMANA',
    }
    item.update(alteracoes)
    return item


def test_holdout_p3_tem_sha_imutavel_e_cobertura_completa():
    politica = carregar_politica_runtime(POLITICA)
    registros, sha256 = carregar_holdout(HOLDOUT)
    assert sha256 == politica.holdout_sha256
    assert validar_holdout_imutavel(HOLDOUT, politica) == sha256
    assert len(registros) == 28
    assert {item.categoria for item in registros} == set(CATEGORIAS)


def test_holdout_p3_bloqueia_mutacao_mesmo_sem_mudar_registros(tmp_path):
    politica = carregar_politica_runtime(POLITICA)
    mutado = tmp_path / 'holdout.jsonl'
    mutado.write_text(HOLDOUT.read_text(encoding='utf-8') + '\n', encoding='utf-8')
    with pytest.raises(ValueError, match='SHA-256 imutável'):
        validar_holdout_imutavel(mutado, politica)


def test_modelo_p2_supera_baseline_no_holdout_p3():
    politica = carregar_politica_runtime(POLITICA)
    holdout, sha256 = carregar_holdout(HOLDOUT)
    modelo = treinar_modelo_runtime(DATASET_P2)
    resultado = avaliar_holdout(
        modelo,
        holdout,
        holdout_sha256=sha256,
        politica=politica,
    )
    assert resultado.status == 'APROVADO'
    assert resultado.modelo_macro_f1 >= 0.80
    assert resultado.ganho_macro_f1 >= 0.10
    assert resultado.modelo_macro_f1 > resultado.baseline_macro_f1
    assert resultado.como_dict()['status'] == 'APROVADO'


def test_amostras_reais_observadas_ficam_fora_do_treino_sem_revisao_humana():
    registros = carregar_amostras_observadas(OBSERVADOS)
    assert len(registros) == 14
    assert all(item.anonimizado for item in registros)
    assert all(item.revisao_status == 'PENDENTE_HUMANA' for item in registros)
    assert amostras_aprovadas_para_treino(registros) == []


def test_amostra_aprovada_so_entra_no_treino_com_revisao_completa(tmp_path):
    caminho = _escrever_jsonl(
        tmp_path / 'observados.jsonl',
        [
            _observado_item(
                revisao_status='APROVADO',
                categoria_revisada='UX',
                revisor_ref='revisor-interno',
            )
        ],
    )
    registros = carregar_amostras_observadas(caminho)
    treino = amostras_aprovadas_para_treino(registros)
    assert len(treino) == 1
    assert treino[0].categoria == 'UX'


def test_amostra_com_pii_detectavel_e_bloqueada(tmp_path):
    caminho = _escrever_jsonl(
        tmp_path / 'observados.jsonl',
        [_observado_item(texto='Solicitante pessoa@example.com precisa acessar a tela.')],
    )
    with pytest.raises(ValueError, match='PII'):
        carregar_amostras_observadas(caminho)


@pytest.mark.parametrize(
    ('alteracoes', 'mensagem'),
    [
        ({'modelo_versao': 'modelo-invalido'}, 'política exige modelo'),
        ({'holdout_versao': 'holdout-invalido'}, 'holdout_versao inválida'),
        ({'holdout_sha256': 'invalido'}, 'holdout_sha256 inválido'),
        ({'modo_padrao': 'invalido'}, 'modo_padrao inválido'),
        ({'canary_percentual': 101}, 'canary_percentual'),
        ({'confianca_minima_modelo': 1.1}, 'confianca_minima_modelo'),
        ({'macro_f1_holdout_minimo': 1.1}, 'macro_f1_holdout_minimo'),
        ({'ganho_f1_holdout_minimo': -0.1}, 'ganho_f1_holdout_minimo'),
        ({'js_divergence_alerta': 1.1}, 'js_divergence_alerta'),
        ({'taxa_baixa_confianca_alerta': 1.1}, 'taxa_baixa_confianca_alerta'),
        ({'minimo_amostras_reais_aprovadas_canary': 0}, 'canary'),
        (
            {
                'minimo_amostras_reais_aprovadas_canary': 5,
                'minimo_amostras_reais_aprovadas_active': 4,
            },
            'active',
        ),
        (
            {'distribuicao_referencia': {'CATEGORIA_DESCONHECIDA': 1}},
            'categorias desconhecidas',
        ),
        (
            {'distribuicao_referencia': {'FUNCIONAL': -1, 'UX': 2}},
            'valores negativos',
        ),
        (
            {'distribuicao_referencia': {categoria: 0 for categoria in CATEGORIAS}},
            'massa positiva',
        ),
    ],
)
def test_politica_runtime_bloqueia_configuracao_invalida(tmp_path, alteracoes, mensagem):
    caminho = _politica_mutada(tmp_path, **alteracoes)
    with pytest.raises(ValueError, match=mensagem):
        carregar_politica_runtime(caminho)


@pytest.mark.parametrize(
    ('conteudo', 'mensagem'),
    [
        ('{json-invalido}\n', 'holdout inválido'),
        (json.dumps({'id': 'x'}) + '\n', 'ausentes'),
        (json.dumps(_holdout_item(texto='')) + '\n', 'valores vazios'),
        (
            json.dumps(_holdout_item()) + '\n' + json.dumps(_holdout_item()) + '\n',
            'id duplicado',
        ),
        (
            json.dumps(_holdout_item(categoria='DESCONHECIDA')) + '\n',
            'categoria desconhecida',
        ),
        (
            json.dumps(_holdout_item(dataset_versao='versao-invalida')) + '\n',
            'versão de holdout inválida',
        ),
    ],
)
def test_holdout_bloqueia_entradas_invalidas(tmp_path, conteudo, mensagem):
    caminho = tmp_path / 'holdout.jsonl'
    caminho.write_text(conteudo, encoding='utf-8')
    with pytest.raises(ValueError, match=mensagem):
        carregar_holdout(caminho)


def test_holdout_bloqueia_arquivo_vazio_e_cobertura_incompleta(tmp_path):
    vazio = tmp_path / 'vazio.jsonl'
    vazio.write_text('', encoding='utf-8')
    with pytest.raises(ValueError, match='não pode ser vazio'):
        carregar_holdout(vazio)

    incompleto = _escrever_jsonl(tmp_path / 'incompleto.jsonl', [_holdout_item()])
    with pytest.raises(ValueError, match='sem cobertura'):
        carregar_holdout(incompleto)


@pytest.mark.parametrize(
    ('alteracoes', 'mensagem'),
    [
        ({'texto': ''}, 'amostra observada inválida'),
        ({'categoria_sugerida': 'DESCONHECIDA'}, 'categoria_sugerida desconhecida'),
        ({'revisao_status': 'AUTO_APROVADO'}, 'revisao_status inválido'),
        ({'anonimizado': False}, 'não anonimizada'),
        (
            {'revisao_status': 'APROVADO', 'categoria_revisada': 'UX'},
            'revisão completa',
        ),
    ],
)
def test_amostras_observadas_bloqueiam_contrato_invalido(tmp_path, alteracoes, mensagem):
    caminho = _escrever_jsonl(
        tmp_path / 'observados.jsonl',
        [_observado_item(**alteracoes)],
    )
    with pytest.raises(ValueError, match=mensagem):
        carregar_amostras_observadas(caminho)


def test_amostras_observadas_bloqueiam_id_duplicado(tmp_path):
    item = _observado_item()
    caminho = _escrever_jsonl(tmp_path / 'observados.jsonl', [item, item])
    with pytest.raises(ValueError, match='id duplicado'):
        carregar_amostras_observadas(caminho)


def test_runtime_off_preserva_baseline():
    politica = carregar_politica_runtime(POLITICA)
    modelo = treinar_modelo_runtime(DATASET_P2)
    decisao = classificar_runtime(
        'O acesso administrativo exige autorização explícita.',
        correlation_id='p3-off-1',
        politica=politica,
        modelo=modelo,
    )
    assert decisao.modo == 'off'
    assert decisao.engine == 'keyword-weighted-v1'
    assert decisao.fallback_reason == 'ML_OFF'
    assert decisao.modelo_categoria is None


def test_runtime_shadow_calcula_modelo_sem_alterar_resposta():
    politica = carregar_politica_runtime(POLITICA)
    modelo = treinar_modelo_runtime(DATASET_P2)
    decisao = classificar_runtime(
        'O serviço envia eventos para uma plataforma externa.',
        correlation_id='p3-shadow-1',
        politica=politica,
        modelo=modelo,
        modo='shadow',
    )
    assert decisao.modo == 'shadow'
    assert decisao.categoria == decisao.baseline_categoria
    assert decisao.modelo_categoria is not None
    assert decisao.fallback_reason == 'SHADOW_ONLY'


def test_runtime_canary_e_bloqueado_sem_amostras_reais_aprovadas():
    politica = replace(carregar_politica_runtime(POLITICA), canary_percentual=100.0)
    modelo = treinar_modelo_runtime(DATASET_P2)
    decisao = classificar_runtime(
        'Mensagens recebidas da fila devem ser convertidas para o contrato interno.',
        correlation_id='p3-canary-blocked',
        politica=politica,
        modelo=modelo,
        modo='canary',
        amostras_reais_aprovadas=0,
    )
    assert decisao.engine == 'keyword-weighted-v1'
    assert decisao.canary_selected is False
    assert decisao.fallback_reason == 'REAL_SAMPLE_GATE_BLOCKED'


def test_runtime_active_e_bloqueado_sem_minimo_de_amostras_reais():
    politica = carregar_politica_runtime(POLITICA)
    modelo = treinar_modelo_runtime(DATASET_P2)
    decisao = classificar_runtime(
        'A API deve integrar com o serviço externo.',
        correlation_id='p3-active-blocked',
        politica=politica,
        modelo=modelo,
        modo='active',
        amostras_reais_aprovadas=politica.minimo_amostras_reais_aprovadas_active - 1,
    )
    assert decisao.fallback_reason == 'REAL_SAMPLE_GATE_BLOCKED'


def test_runtime_canary_100_porcento_usa_modelo_apos_gate_humano():
    politica = replace(carregar_politica_runtime(POLITICA), canary_percentual=100.0)
    modelo = treinar_modelo_runtime(DATASET_P2)
    decisao = classificar_runtime(
        'Mensagens recebidas da fila devem ser convertidas para o contrato interno.',
        correlation_id='p3-canary-1',
        politica=politica,
        modelo=modelo,
        modo='canary',
        amostras_reais_aprovadas=politica.minimo_amostras_reais_aprovadas_canary,
    )
    assert decisao.canary_selected is True
    assert decisao.engine == 'multinomial-nb-word-char-ngram-v1'
    assert decisao.fallback_reason is None


def test_runtime_canary_zero_porcento_preserva_baseline_apos_gate_humano():
    politica = replace(carregar_politica_runtime(POLITICA), canary_percentual=0.0)
    modelo = treinar_modelo_runtime(DATASET_P2)
    decisao = classificar_runtime(
        'Mensagens recebidas da fila devem ser convertidas para o contrato interno.',
        correlation_id='p3-canary-zero',
        politica=politica,
        modelo=modelo,
        modo='canary',
        amostras_reais_aprovadas=politica.minimo_amostras_reais_aprovadas_canary,
    )
    assert decisao.canary_selected is False
    assert decisao.fallback_reason == 'CANARY_NOT_SELECTED'
    assert decisao.engine == 'keyword-weighted-v1'


def test_runtime_active_usa_modelo_quando_gates_estao_satisfeitos():
    politica = replace(carregar_politica_runtime(POLITICA), confianca_minima_modelo=0.0)
    modelo = treinar_modelo_runtime(DATASET_P2)
    decisao = classificar_runtime(
        'O acesso deve exigir autenticação MFA e auditoria.',
        correlation_id='p3-active-1',
        politica=politica,
        modelo=modelo,
        modo='active',
        amostras_reais_aprovadas=politica.minimo_amostras_reais_aprovadas_active,
    )
    assert decisao.canary_selected is True
    assert decisao.fallback_reason is None
    assert decisao.engine == 'multinomial-nb-word-char-ngram-v1'


def test_runtime_active_faz_fallback_quando_threshold_de_confianca_nao_e_atendido():
    politica = replace(carregar_politica_runtime(POLITICA), confianca_minima_modelo=1.0)
    modelo = treinar_modelo_runtime(DATASET_P2)
    decisao = classificar_runtime(
        'xyz qwerty elemento desconhecido',
        correlation_id='p3-low-confidence-1',
        politica=politica,
        modelo=modelo,
        modo='active',
        amostras_reais_aprovadas=politica.minimo_amostras_reais_aprovadas_active,
    )
    assert decisao.engine == 'keyword-weighted-v1'
    assert decisao.fallback_reason == 'LOW_CONFIDENCE'
    assert decisao.modelo_confianca is not None
    assert decisao.modelo_confianca < politica.confianca_minima_modelo


def test_runtime_bloqueia_parametros_invalidos():
    politica = carregar_politica_runtime(POLITICA)
    modelo = treinar_modelo_runtime(DATASET_P2)
    with pytest.raises(ValueError, match='correlation_id'):
        classificar_runtime('', correlation_id=' ', politica=politica, modelo=modelo)
    with pytest.raises(ValueError, match='modo de runtime inválido'):
        classificar_runtime(
            'Requisito válido',
            correlation_id='p3-invalid-mode',
            politica=politica,
            modelo=modelo,
            modo='automatico',
        )
    with pytest.raises(ValueError, match='não pode ser negativo'):
        classificar_runtime(
            'Requisito válido',
            correlation_id='p3-negative-samples',
            politica=politica,
            modelo=modelo,
            amostras_reais_aprovadas=-1,
        )


def test_runtime_faz_fallback_quando_modelo_lanca_erro():
    class ModeloComErro:
        def classificar(self, _texto):
            raise RuntimeError('falha simulada')

    politica = carregar_politica_runtime(POLITICA)
    decisao = classificar_runtime(
        'O sistema deve permitir consultar demandas.',
        correlation_id='p3-model-error',
        politica=politica,
        modelo=ModeloComErro(),
        modo='shadow',
    )
    assert decisao.engine == 'keyword-weighted-v1'
    assert decisao.fallback_reason == 'ML_RUNTIME_ERROR:RuntimeError'


def test_drift_balanceado_nao_gera_alerta():
    politica = carregar_politica_runtime(POLITICA)
    eventos = [
        EventoClassificacaoML(categoria=categoria, confianca=0.90, engine='ml')
        for categoria in CATEGORIAS
    ]
    resultado = calcular_drift(eventos, politica=politica)
    assert resultado.js_divergence < politica.js_divergence_alerta
    assert resultado.taxa_baixa_confianca == 0
    assert resultado.alertas == []
    assert resultado.como_dict()['total'] == len(CATEGORIAS)


def test_drift_concentrado_em_uma_categoria_gera_alerta():
    politica = carregar_politica_runtime(POLITICA)
    eventos = [
        EventoClassificacaoML(categoria='FUNCIONAL', confianca=0.90, engine='ml')
        for _ in range(14)
    ]
    resultado = calcular_drift(eventos, politica=politica)
    assert resultado.js_divergence >= politica.js_divergence_alerta
    assert 'CATEGORY_DISTRIBUTION_DRIFT' in resultado.alertas


def test_drift_baixa_confianca_gera_alerta():
    politica = carregar_politica_runtime(POLITICA)
    eventos = [
        EventoClassificacaoML(categoria='FUNCIONAL', confianca=0.0, engine='ml')
        for _ in range(4)
    ]
    resultado = calcular_drift(eventos, politica=politica)
    assert resultado.taxa_baixa_confianca == 1.0
    assert 'LOW_CONFIDENCE_RATE' in resultado.alertas


def test_drift_bloqueia_eventos_vazios_e_categoria_desconhecida():
    politica = carregar_politica_runtime(POLITICA)
    with pytest.raises(ValueError, match='ao menos um evento'):
        calcular_drift([], politica=politica)
    with pytest.raises(ValueError, match='categorias desconhecidas'):
        calcular_drift(
            [EventoClassificacaoML(categoria='OUTRA', confianca=0.9, engine='ml')],
            politica=politica,
        )
