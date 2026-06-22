from app.services.actions_runtime_monitor import classificar_runs, montar_snapshot_operacional, normalizar_run


def test_normaliza_run_e_classifica_success():
    run = normalizar_run(
        {
            'id': 123,
            'name': 'CI',
            'status': 'completed',
            'conclusion': 'success',
            'head_branch': 'main',
            'event': 'push',
            'head_sha': 'abc',
            'html_url': 'https://example.com/run/123',
        }
    )

    assert run.run_id == 123
    assert run.workflow == 'CI'
    assert run.health == 'healthy'


def test_snapshot_identifica_falha_operacional():
    snapshot = montar_snapshot_operacional(
        [
            {'id': 1, 'name': 'CI', 'status': 'completed', 'conclusion': 'success'},
            {'id': 2, 'name': 'Deploy', 'status': 'completed', 'conclusion': 'failure'},
        ]
    )

    assert snapshot['total_runs'] == 2
    assert snapshot['score_saude'] == 50.0
    assert snapshot['por_status_operacional']['unhealthy'] == 1
    assert snapshot['decisao'] == 'corrigir_falhas_de_actions_antes_de_novo_merge'


def test_classifica_workflow_em_execucao():
    run = normalizar_run({'id': 3, 'name': 'Dispatcher', 'status': 'in_progress', 'conclusion': None})
    resumo = classificar_runs([run])

    assert resumo['por_status_operacional']['running'] == 1
    assert resumo['decisao'] == 'aguardar_finalizacao_dos_workflows'
