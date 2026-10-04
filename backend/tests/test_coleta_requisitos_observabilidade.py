"""Testes determinísticos das métricas da coleta governada."""

import json
from datetime import UTC, datetime, timedelta

from app.models.auditoria import AuditoriaEvento
from app.services.coleta_requisitos_observabilidade import (
    ACAO_COLETA_AVALIADA,
    ACAO_REQUISITO_GERADO,
    calcular_metricas_coleta_requisitos,
)


def _evento(*, acao, chave, instante, **dados):
    payload = {
        'schema_version': '1.0.0',
        'chave_idempotencia_hash': chave,
        **dados,
    }
    return AuditoriaEvento(
        correlation_id=f'corr-{chave}',
        usuario='teste',
        acao=acao,
        entidade='coleta_requisito' if acao == ACAO_COLETA_AVALIADA else 'requisito',
        entidade_id=chave if acao == ACAO_COLETA_AVALIADA else '1',
        payload_minimo=json.dumps(payload),
        criado_em=instante,
    )


def test_metricas_consolidam_primeira_submissao_refinamento_e_origem(db_session):
    agora = datetime.now(UTC)

    # A: precisou refinamento e depois gerou.
    db_session.add_all([
        _evento(
            acao=ACAO_COLETA_AVALIADA,
            chave='A' * 64,
            instante=agora - timedelta(hours=4),
            origem='reqsys',
            pontuacao=68,
            classificacao='refinamento',
            pronto_para_gerar=False,
            codigos_pendencia=['CRITERIOS_ACEITE_INSUFICIENTES'],
        ),
        _evento(
            acao=ACAO_COLETA_AVALIADA,
            chave='A' * 64,
            instante=agora - timedelta(hours=2),
            origem='reqsys',
            pontuacao=92,
            classificacao='ouro',
            pronto_para_gerar=True,
            codigos_pendencia=[],
        ),
        _evento(
            acao=ACAO_REQUISITO_GERADO,
            chave='A' * 64,
            instante=agora - timedelta(hours=2),
            origem='reqsys',
            pontuacao=92,
            classificacao='ouro',
        ),
    ])

    # B: aprovado na primeira submissão.
    db_session.add_all([
        _evento(
            acao=ACAO_COLETA_AVALIADA,
            chave='B' * 64,
            instante=agora - timedelta(hours=1),
            origem='microsoft_forms',
            pontuacao=90,
            classificacao='ouro',
            pronto_para_gerar=True,
            codigos_pendencia=[],
        ),
        _evento(
            acao=ACAO_REQUISITO_GERADO,
            chave='B' * 64,
            instante=agora - timedelta(minutes=50),
            origem='microsoft_forms',
            pontuacao=90,
            classificacao='ouro',
        ),
    ])

    # C: ainda em refinamento e compõe as pendências atuais.
    db_session.add(
        _evento(
            acao=ACAO_COLETA_AVALIADA,
            chave='C' * 64,
            instante=agora - timedelta(minutes=30),
            origem='power_apps',
            pontuacao=65,
            classificacao='refinamento',
            pronto_para_gerar=False,
            codigos_pendencia=[
                'REGRAS_NEGOCIO_NAO_INFORMADAS',
                'CRITERIOS_ACEITE_INSUFICIENTES',
            ],
        )
    )
    db_session.commit()

    metricas = calcular_metricas_coleta_requisitos(db_session, janela_dias=30)

    assert metricas['coletas_total'] == 3
    assert metricas['avaliacoes_total'] == 4
    assert metricas['requisitos_gerados'] == 2
    assert metricas['em_refinamento'] == 1
    assert metricas['taxa_aprovacao_primeira_submissao_percentual'] == 33.33
    assert metricas['pontuacao_media_atual'] == 82.33
    assert metricas['tempo_medio_refinamento_minutos'] == 120.0
    assert metricas['cobertura_avaliacao_das_geracoes_percentual'] == 100.0
    assert metricas['sem_dados'] is False

    origens = {item['origem']: item['quantidade'] for item in metricas['origens']}
    assert origens == {'reqsys': 1, 'microsoft_forms': 1, 'power_apps': 1}

    pendencias = {item['codigo']: item['quantidade'] for item in metricas['principais_pendencias']}
    assert pendencias['REGRAS_NEGOCIO_NAO_INFORMADAS'] == 1
    assert pendencias['CRITERIOS_ACEITE_INSUFICIENTES'] == 1


def test_metricas_sem_eventos_nao_inventam_percentuais(db_session):
    metricas = calcular_metricas_coleta_requisitos(db_session, janela_dias=30)

    assert metricas['sem_dados'] is True
    assert metricas['coletas_total'] == 0
    assert metricas['taxa_aprovacao_primeira_submissao_percentual'] is None
    assert metricas['pontuacao_media_atual'] is None
    assert metricas['tempo_medio_refinamento_minutos'] is None
