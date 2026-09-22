"""Caminhos críticos — RBAC."""

from app.services.rbac import permissoes, tem_permissao


def test_permissoes_retorna_vazio_para_papel_desconhecido():
    assert permissoes('visitante') == []


def test_tem_permissao_negado_para_escopo_inexistente():
    assert tem_permissao('analista', 'auditoria:read') is False


def test_tem_permissao_concedido_para_admin():
    assert tem_permissao('admin', 'auditoria:read') is True
