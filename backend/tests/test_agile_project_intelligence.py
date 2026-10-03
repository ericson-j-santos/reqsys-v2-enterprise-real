from app.services.agile_project_intelligence import AgileProjectDemand, gerar_pacote_agil


def test_gera_pacote_negocial_tecnico_e_scrum():
    pacote = gerar_pacote_agil(AgileProjectDemand(
        titulo='Automatizar aprovação de requisitos',
        descricao=(
            'O analista precisa reduzir o prazo de aprovação e dar visibilidade ao gestor. '
            'A API deve persistir o histórico no SQL e registrar logs com correlation_id. '
            'O pipeline CI deve executar testes automatizados antes do deploy.'
        ),
        objetivo='Reduzir o lead time e o retrabalho da aprovação.',
        publico_alvo='analista de requisitos',
        owner='Product Owner',
        prioridade='alta',
        correlation_id='corr-123',
    ))

    assert pacote['schema_version'] == '1.0.0'
    assert pacote['package_id'].startswith('agile-')
    assert pacote['correlation_id'] == 'corr-123'
    assert pacote['project']['owner'] == 'Product Owner'
    assert pacote['business']['requirements']
    assert any('API' in item for item in pacote['technical']['requirements'])
    assert any('pipeline CI' in item for item in pacote['technical']['requirements'])
    assert pacote['scrum']['epic'] == 'Automatizar aprovação de requisitos'
    assert pacote['scrum']['user_story'].startswith('Como analista de requisitos')
    assert pacote['scrum']['acceptance_criteria']
    assert pacote['scrum']['sprint_recommendation'] == 'proxima_sprint'
    assert pacote['governance']['gaps'] == []
    assert pacote['governance']['next_action'] == 'priorizar_no_backlog'


def test_sinaliza_gaps_antes_de_sugerir_sprint():
    pacote = gerar_pacote_agil(AgileProjectDemand(
        titulo='Melhorar processo de atendimento',
        descricao='O usuário precisa acompanhar o andamento da solicitação.',
    ))

    assert pacote['technical']['requirements'] == []
    assert 'owner_nao_definido' in pacote['governance']['gaps']
    assert 'publico_alvo_nao_definido' in pacote['governance']['gaps']
    assert 'requisitos_tecnicos_insuficientes' in pacote['governance']['gaps']
    assert pacote['scrum']['sprint_recommendation'] == 'refinamento'
    assert pacote['governance']['risk_level'] == 'medio'


def test_package_id_e_deterministico_para_idempotencia():
    demanda = AgileProjectDemand(
        titulo='Gerar backlog estruturado',
        descricao='O analista precisa gerar histórias. A API deve expor o resultado.',
        objetivo='Acelerar o refinamento.',
    )

    primeiro = gerar_pacote_agil(demanda)
    segundo = gerar_pacote_agil(demanda)

    assert primeiro['package_id'] == segundo['package_id']
