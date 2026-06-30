"""Caminhos críticos — runtime remediation governada."""

from app.core.runtime_remediation import (
    RemediationRequest,
    avaliar_remediacao,
    criar_health_snapshot_base,
)


def _request(**kwargs) -> RemediationRequest:
    base = {
        'codigo_acao': 'ACAO-TEST',
        'componente': 'api_fastapi',
        'tipo': 'observacao',
        'motivo': 'teste governado',
        'dry_run': True,
    }
    base.update(kwargs)
    return RemediationRequest(**base)


def test_criar_health_snapshot_base_expoe_componentes():
    snapshot = criar_health_snapshot_base('corr-rem', 'test')
    assert snapshot.correlation_id == 'corr-rem'
    assert len(snapshot.componentes) >= 4
    assert snapshot.bloqueios_operacionais


def test_avaliar_remediacao_componente_desconhecido():
    health = criar_health_snapshot_base('corr-rem-1', 'test')
    decisao = avaliar_remediacao(
        _request(componente='inexistente'),
        health,
        'corr-rem-1',
    )
    assert decisao.permitido is False
    assert decisao.estado == 'bloqueado_por_politica'


def test_avaliar_remediacao_bloqueia_execucao_real():
    health = criar_health_snapshot_base('corr-rem-2', 'test')
    decisao = avaliar_remediacao(_request(dry_run=False), health, 'corr-rem-2')
    assert decisao.permitido is False
    assert 'dry_run' in decisao.razoes[0]


def test_avaliar_remediacao_bloqueia_restart_e_rollback():
    health = criar_health_snapshot_base('corr-rem-3', 'test')
    for tipo in ('restart_controlado', 'rollback_seguro'):
        decisao = avaliar_remediacao(_request(tipo=tipo), health, 'corr-rem-3')
        assert decisao.permitido is False
        assert decisao.politica_aplicada == 'AOP-RUN-DESTRUCTIVE-BLOCK-001'


def test_avaliar_remediacao_permite_retry_governado_dry_run():
    health = criar_health_snapshot_base('corr-rem-4', 'test')
    decisao = avaliar_remediacao(_request(tipo='retry_governado'), health, 'corr-rem-4')
    assert decisao.permitido is True
    assert decisao.estado == 'permitido_dry_run'
    assert decisao.comandos_planejados


def test_avaliar_remediacao_permite_acoes_nao_destrutivas():
    health = criar_health_snapshot_base('corr-rem-5', 'test')
    for tipo in ('bloquear_deploy', 'registrar_incidente', 'observacao'):
        decisao = avaliar_remediacao(_request(tipo=tipo), health, 'corr-rem-5')
        assert decisao.permitido is True
        assert decisao.politica_aplicada == 'AOP-RUN-GOVERNED-NON-DESTRUCTIVE-001'


def test_avaliar_remediacao_classificacao_score_critico():
    from app.core.runtime_remediation import _classificar_estado_por_score

    assert _classificar_estado_por_score(0) == 'desconhecido'
    assert _classificar_estado_por_score(50) == 'critico'
    assert _classificar_estado_por_score(70) == 'degradado'
    assert _classificar_estado_por_score(90) == 'saudavel'
