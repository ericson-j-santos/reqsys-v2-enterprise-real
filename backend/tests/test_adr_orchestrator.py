from app.services.adr_orchestrator import (
    AdrDemand,
    analytics_adrs,
    analytics_coordinators,
    analytics_risk,
    analytics_summary,
    coordenar_e_persistir_demanda,
    coordenar_e_persistir_lote,
    coordenar_geral,
    coordenar_lote,
    listar_coordenadores_adr,
)


def test_classificador_direciona_lgpd_para_adr_002():
    rota = coordenar_geral(AdrDemand(
        titulo='Log expõe CPF e token em texto puro',
        descricao='Precisamos mascarar dado sensivel e pii antes de persistir o log.',
        ambiente='prod',
    ))

    assert rota['adr_primario']['adr_id'] == 'ADR-002'
    assert 'ambiente:prod' in rota['labels']
    assert rota['governanca']['permite_acao_destrutiva'] is False


def test_classificador_sem_match_cai_no_intake_central():
    rota = coordenar_geral(AdrDemand(titulo='oi', descricao=''))

    assert rota['adr_primario']['adr_id'] == 'ADR-000'
    assert rota['adr_primario']['coordinator_id'] == 'adr-intake-coordinator'
    assert rota['multi_adr'] is False


def test_violacao_de_gate_forca_risco_critico_e_aprovacao_humana():
    rota = coordenar_geral(AdrDemand(
        titulo='Config de ambiente',
        descricao='cors * liberado e auth_enabled=false em producao',
    ))

    assert rota['violacoes_detectadas']
    assert rota['nivel_risco'] == 'critico'
    assert rota['governanca']['requer_aprovacao_humana'] is True
    assert rota['governanca']['nivel_autonomia_sugerido'] == 'N0'


def test_orchestrator_expoe_catalogo_com_doze_adrs():
    coordenadores = listar_coordenadores_adr()
    ids = {c['adr_id'] for c in coordenadores}

    assert len(coordenadores) == 12
    assert 'ADR-001' in ids
    assert 'ADR-012' in ids


def test_coordenar_lote_agrega_por_adr():
    resultado = coordenar_lote([
        AdrDemand(titulo='JWT e RBAC sem validacao de issuer'),
        AdrDemand(titulo='Auditoria sem correlation_id propagado'),
    ])

    assert resultado['total'] == 2
    assert resultado['por_adr']['ADR-004'] == 1
    assert resultado['por_adr']['ADR-003'] == 1


def test_persistir_demanda_grava_evento_e_retorna_id(db_session):
    rota = coordenar_e_persistir_demanda(db_session, AdrDemand(
        titulo='Revisar CORS aberto e auth desligada',
        descricao='cors * liberado, auth_enabled=false',
        correlation_id='corr-adr-001',
    ))

    assert rota['coordination_event_id'] > 0
    assert rota['correlation_id'] == 'corr-adr-001'


def test_analytics_summary_reflete_eventos_persistidos(db_session):
    coordenar_e_persistir_lote(db_session, [
        AdrDemand(titulo='Documentar changelog e readme', descricao='atualizar mermaid'),
        AdrDemand(titulo='Revisar JWT sem validacao de issuer e RBAC de admin', descricao='autenticacao e autorizacao criticas'),
    ])

    summary = analytics_summary(db_session)
    assert summary['total_eventos'] == 2
    assert summary['confianca_media'] > 0

    adrs = analytics_adrs(db_session)['adrs']
    assert any(item['valor'] == 'ADR-012' for item in adrs)

    coordinators = analytics_coordinators(db_session)['coordinators']
    assert any(item['valor'] == 'adr-004-coordinator' for item in coordinators)


def test_analytics_risk_conta_apenas_eventos_com_violacao_real(db_session):
    coordenar_e_persistir_demanda(db_session, AdrDemand(
        titulo='Documentar changelog e readme', descricao='atualizar mermaid',
    ))
    coordenar_e_persistir_demanda(db_session, AdrDemand(
        titulo='CORS aberto em producao', descricao='cors * liberado, auth_enabled=false',
    ))

    risk = analytics_risk(db_session)['risk']

    assert risk['nivel_critico'] == 1
    assert risk['com_violacao_de_gate'] == 1
