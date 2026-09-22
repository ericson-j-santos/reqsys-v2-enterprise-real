from app.services.increment_gate_service import verificar_increment_gate


def test_increment_gate_relaxado_sem_coordenador_explicito_em_teste():
    gate = verificar_increment_gate('new_front')
    assert gate['permitido'] is True
    assert gate['motivo'] == 'gate_relaxado_sem_relatorio'
