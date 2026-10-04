from app.api import requisitos
from app.api.requisitos_runtime_transition import _ROUTE_NAME

_RUNTIME_TRANSITION_PATH = '/api/requisitos/{identificador}/transicao'


def test_runtime_transition_route_eh_instalada_antes_da_rota_legada():
    rotas_transicao = [
        route for route in requisitos.api_router.routes
        if getattr(route, 'path', None) == _RUNTIME_TRANSITION_PATH
    ]

    assert rotas_transicao
    assert rotas_transicao[0].name == _ROUTE_NAME
    assert 'POST' in rotas_transicao[0].methods


def test_runtime_transition_route_preserva_rota_legada_como_fallback():
    nomes = [
        route.name for route in requisitos.api_router.routes
        if getattr(route, 'path', None) == _RUNTIME_TRANSITION_PATH
    ]

    assert _ROUTE_NAME in nomes
    assert 'transicionar_requisito' in nomes
