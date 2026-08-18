from unittest.mock import patch

from app.services.role_resolution import resolver_papel


def test_binding_explicito_concede_admin():
    with patch('app.services.role_resolution.get_secret') as get_secret:
        get_secret.side_effect = lambda nome, default='': (
            '{"admin@example.com":"admin"}' if nome == 'REQSYS_ROLE_BINDINGS' else default
        )
        resolucao = resolver_papel('ADMIN@example.com')

    assert resolucao.papel == 'admin'
    assert resolucao.origem == 'configured_identity'


def test_role_entra_mapeada_concede_admin_sem_depender_do_email():
    with patch('app.services.role_resolution.get_secret') as get_secret:
        get_secret.side_effect = lambda nome, default='': default
        resolucao = resolver_papel('usuario@example.com', entra_roles=['ReqSys.Admin'])

    assert resolucao.papel == 'admin'
    assert resolucao.origem == 'entra_app_role'


def test_usuario_nao_mapeado_recebe_papel_nao_privilegiado():
    with patch('app.services.role_resolution.get_secret') as get_secret:
        get_secret.side_effect = lambda nome, default='': default
        resolucao = resolver_papel('nao-mapeado@example.com')

    assert resolucao.papel == 'analista'
    assert resolucao.origem == 'default_fail_closed'


def test_default_admin_e_rebaixado_para_analista():
    def segredo(nome, default=''):
        if nome == 'REQSYS_DEFAULT_ROLE':
            return 'admin'
        return default

    with patch('app.services.role_resolution.get_secret', side_effect=segredo):
        resolucao = resolver_papel('nao-mapeado@example.com')

    assert resolucao.papel == 'analista'
    assert resolucao.origem == 'default_fail_closed'


def test_binding_com_papel_invalido_nao_eleva_privilegio():
    def segredo(nome, default=''):
        if nome == 'REQSYS_ROLE_BINDINGS':
            return '{"usuario@example.com":"superadmin"}'
        return default

    with patch('app.services.role_resolution.get_secret', side_effect=segredo):
        resolucao = resolver_papel('usuario@example.com')

    assert resolucao.papel == 'analista'
    assert resolucao.origem == 'default_fail_closed'


def test_configuracao_json_invalida_falha_fechada():
    with patch('app.services.role_resolution.get_secret', return_value='{invalido'):
        resolucao = resolver_papel('usuario@example.com')

    assert resolucao.papel == 'analista'
    assert resolucao.origem == 'default_fail_closed'
