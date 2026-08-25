from pathlib import Path

import pytest

from app.services.requisito_ml import (
    MODELO_VERSAO,
    ClassificadorRequisitoSupervisionado,
    RegistroTreinoML,
    avaliar_promocao_ml,
    carregar_dataset_ml,
    carregar_politica_ml,
)

DATA_ROOT = Path(__file__).resolve().parents[1] / 'data/ml'
DATASET = DATA_ROOT / 'requisitos_classificador_v1.jsonl'
POLITICA = DATA_ROOT / 'politica_promocao_requisitos_v1.json'


def test_modelo_rejeita_predicao_sem_treino():
    modelo = ClassificadorRequisitoSupervisionado(categorias=('A', 'B'))
    with pytest.raises(RuntimeError, match='ainda não foi treinado'):
        modelo.classificar('texto qualquer')


def test_modelo_rejeita_categoria_desconhecida():
    modelo = ClassificadorRequisitoSupervisionado(categorias=('A', 'B'))
    registros = [
        RegistroTreinoML('exemplo a', 'A'),
        RegistroTreinoML('exemplo b', 'B'),
        RegistroTreinoML('exemplo c', 'C'),
    ]
    with pytest.raises(ValueError, match='categorias de treino desconhecidas'):
        modelo.treinar(registros)


def test_modelo_exige_exemplo_para_todas_as_categorias():
    modelo = ClassificadorRequisitoSupervisionado(categorias=('A', 'B'))
    with pytest.raises(ValueError, match='categorias sem exemplos de treino'):
        modelo.treinar([RegistroTreinoML('apenas classe a', 'A')])


def test_modelo_supervisionado_aprende_contexto_rotulado():
    modelo = ClassificadorRequisitoSupervisionado(categorias=('SEGURANCA', 'UX')).treinar(
        [
            RegistroTreinoML('credenciais protegidas acesso privilegiado', 'SEGURANCA'),
            RegistroTreinoML('sessão bloqueia acesso indevido', 'SEGURANCA'),
            RegistroTreinoML('navegação teclado contraste leitura', 'UX'),
            RegistroTreinoML('foco teclado leitura acessível', 'UX'),
        ]
    )

    resultado = modelo.classificar('navegação por teclado com foco previsível')

    assert resultado.categoria == 'UX'
    assert resultado.confianca > 0.5
    assert resultado.modelo == MODELO_VERSAO
    assert resultado.evidencias


def test_dataset_versionado_e_gate_p2_aprovam_promocao():
    registros, sha256 = carregar_dataset_ml(DATASET)
    politica = carregar_politica_ml(POLITICA)

    resultado, modelo = avaliar_promocao_ml(
        registros,
        dataset_sha256=sha256,
        politica=politica,
    )

    assert len(registros) == 84
    assert resultado.quantidade_treino == 56
    assert resultado.quantidade_validacao == 28
    assert resultado.status == 'APROVADO'
    assert resultado.modelo.macro_f1 >= politica.macro_f1_minimo
    assert resultado.ganho_macro_f1 >= politica.ganho_macro_f1_minimo
    assert resultado.modelo.macro_f1 > resultado.baseline.macro_f1
    assert all(resultado.criterios.values())
    assert modelo.exportar_estado()['modelo_versao'] == MODELO_VERSAO
