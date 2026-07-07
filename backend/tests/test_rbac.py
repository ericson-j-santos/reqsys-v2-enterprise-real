"""Testes do RBAC e da camada de compatibilidade com a taxonomia padrao ADR-004."""

import pytest

from app.services.rbac import (
    PapelPadrao,
    papel_canonico,
    permissoes,
    tem_permissao,
)


@pytest.mark.parametrize('papel', ['admin', 'analista', 'auditor', 'gestor'])
def test_papeis_legados_continuam_com_permissoes_inalteradas(papel):
    """Papeis legados sao os valores reais emitidos em JWT/frontend hoje — nao podem mudar."""
    assert permissoes(papel) != []
    assert 'dashboard:read' in permissoes(papel)


def test_admin_mantem_permissoes_completas():
    escopos = permissoes('admin')
    assert 'demanda:aprovar' in escopos
    assert 'dossie:arquivar' in escopos


@pytest.mark.parametrize(
    'papel_legado,esperado',
    [
        ('admin', PapelPadrao.ADMIN),
        ('analista', PapelPadrao.ANALYST),
        ('auditor', PapelPadrao.SECURITY),
        ('gestor', PapelPadrao.RUNTIME_OPERATOR),
    ],
)
def test_papel_canonico_traduz_legado_para_taxonomia_adr004(papel_legado, esperado):
    assert papel_canonico(papel_legado) == esperado.value


def test_papel_canonico_aceita_nome_ja_canonico():
    assert papel_canonico('ADMIN') == 'ADMIN'
    assert papel_canonico('SECURITY') == 'SECURITY'


def test_papel_canonico_desconhecido_retorna_proprio_valor():
    assert papel_canonico('estagiario') == 'estagiario'


def test_permissoes_aceita_nome_canonico_equivalente_ao_legado():
    """permissoes('SECURITY') deve resolver para o mesmo conjunto de 'auditor'."""
    assert permissoes('SECURITY') == permissoes('auditor')
    assert permissoes('ADMIN') == permissoes('admin')
    assert permissoes('RUNTIME_OPERATOR') == permissoes('gestor')
    assert permissoes('ANALYST') == permissoes('analista')


def test_viewer_e_ai_governor_sao_papeis_novos_sem_equivalente_legado():
    viewer = permissoes('VIEWER')
    ai_governor = permissoes('AI_GOVERNOR')

    assert viewer == ['dashboard:read', 'rastreabilidade:read', 'relatorios:read']
    assert 'ia:governanca:aprovar' in ai_governor
    assert 'requisitos:write' not in viewer  # somente leitura


def test_tem_permissao_funciona_com_papel_legado_e_canonico():
    assert tem_permissao('admin', 'demanda:aprovar') is True
    assert tem_permissao('ADMIN', 'demanda:aprovar') is True
    assert tem_permissao('VIEWER', 'requisitos:write') is False


def test_papel_desconhecido_nao_tem_permissoes():
    assert permissoes('papel-inexistente') == []
    assert tem_permissao('papel-inexistente', 'dashboard:read') is False
