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


def test_amostras_reais_observadas_ficam_fora_do_treino_sem_revisao_humana():
    registros = carregar_amostras_observadas(OBSERVADOS)
    assert len(registros) == 14
    assert all(item.anonimizado for item in registros)
    assert all(item.revisao_status == 'PENDENTE_HUMANA' for item in registros)
    assert amostras_aprovadas_para_treino(registros) == []


def test_amostra_com_pii_detectavel_e_bloqueada(tmp_path):
    caminho = tmp_path / 'observados.jsonl'
    caminho.write_text(
        json.dumps(
            {
                'id': 'obs-1',
                'texto': 'Solicitante pessoa@example.com precisa acessar a tela.',
                'source_ref': 'teste',
                'categoria_sugerida': 'UX',
                'anonimizado': True,
                'revisao_status': 'PENDENTE_HUMANA',
            },
            ensure_ascii=False,
        ) + '\n',
        encoding='utf-8',
    )
    with pytest.raises(ValueError, match='PII'):
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


def test_runtime_active_faz_fallback_por_baixa_confianca_apos_gate_humano():
    politica = carregar_politica_runtime(POLITICA)
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


def test_drift_concentrado_em_uma_categoria_gera_alerta():
    politica = carregar_politica_runtime(POLITICA)
    eventos = [
        EventoClassificacaoML(categoria='FUNCIONAL', confianca=0.90, engine='ml')
        for _ in range(14)
    ]
    resultado = calcular_drift(eventos, politica=politica)
    assert resultado.js_divergence >= politica.js_divergence_alerta
    assert 'CATEGORY_DISTRIBUTION_DRIFT' in resultado.alertas
