from pathlib import Path

import pytest

from copilot_memory_core import (
    STATUS_PENDENTE,
    STATUS_SINCRONIZADO,
    aplicar_decisao_planner,
    avaliar_planner_durante_pendencia,
    content_hash,
    gerar_memory_id,
    hash_json,
    montar_snapshot,
    planner_hash,
)


def test_hash_json_e_deterministico_independente_da_ordem():
    assert hash_json({'b': 2, 'a': 1}) == hash_json({'a': 1, 'b': 2})


def test_memory_id_e_estavel_e_nao_expoe_task_id():
    primeiro = gerar_memory_id('task-corporativa-123')
    segundo = gerar_memory_id('task-corporativa-123')
    assert primeiro == segundo
    assert primeiro.startswith('planner-')
    assert 'task-corporativa' not in primeiro


def test_montar_snapshot_mescla_sem_apagar_campos_ausentes():
    atual = montar_snapshot({
        'planner_task_id': 'task-1',
        'assunto': 'Assunto original',
        'decisao': 'Manter fluxo',
        'planner_percentual': 10,
    })
    novo = montar_snapshot({'planner_percentual': 50}, atual)

    assert novo['assunto'] == 'Assunto original'
    assert novo['decisao'] == 'Manter fluxo'
    assert novo['planner_percentual'] == 50
    assert content_hash(novo) != content_hash(atual)


def test_percentual_invalido_falha_fechado():
    with pytest.raises(ValueError):
        montar_snapshot({'planner_percentual': 101})


def test_planner_pendente_reconhece_eco_sem_conflito():
    payload = {
        'planner_titulo': 'Tarefa',
        'planner_status': 'em_andamento',
        'planner_percentual': 30,
        'planner_prazo': '2026-09-10',
    }
    aplicado = planner_hash(payload)
    assert avaliar_planner_durante_pendencia(payload, aplicado) == 'eco'


def test_planner_pendente_detecta_alteracao_concorrente():
    anterior = {
        'planner_titulo': 'Tarefa',
        'planner_status': 'em_andamento',
        'planner_percentual': 30,
        'planner_prazo': '2026-09-10',
    }
    recebido = dict(anterior, planner_percentual=60)
    assert avaliar_planner_durante_pendencia(recebido, planner_hash(anterior)) == 'conflito'


def test_comando_planner_so_e_emitido_com_task_id():
    with pytest.raises(ValueError):
        aplicar_decisao_planner(
            origem='excel',
            solicitar_planner=True,
            planner_task_id=None,
            novo_planner_hash='novo',
            planner_applied_hash='antigo',
        )


def test_comando_planner_diferente_fica_pendente_e_igual_fica_sincronizado():
    pendente = aplicar_decisao_planner(
        origem='excel',
        solicitar_planner=True,
        planner_task_id='task-1',
        novo_planner_hash='novo',
        planner_applied_hash='antigo',
    )
    assert pendente['planner_sync_status'] == STATUS_PENDENTE
    assert pendente['atualizar_planner'] is True

    sincronizado = aplicar_decisao_planner(
        origem='excel',
        solicitar_planner=True,
        planner_task_id='task-1',
        novo_planner_hash='mesmo',
        planner_applied_hash='mesmo',
    )
    assert sincronizado['planner_sync_status'] == STATUS_SINCRONIZADO
    assert sincronizado['atualizar_planner'] is False


def test_core_nao_importa_reqsys_fastapi_ou_sqlalchemy():
    source = (Path(__file__).parents[1] / 'copilot_memory_core' / 'engine.py').read_text(encoding='utf-8').lower()
    assert 'sqlalchemy' not in source
    assert 'fastapi' not in source
    assert 'from app.' not in source
    assert 'import app.' not in source
