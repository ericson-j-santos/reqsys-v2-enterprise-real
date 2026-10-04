"""Construcao de Adaptive Cards para eventos de status de requisito enviados ao Teams.

Layout (Container com cor de status + ColumnSet + FactSet, sem imagem de
criador) reproduz o formato confirmado ao vivo em `robo_envia_teamsv2`
(ver scripts/update_teams_v2_adaptive_card.py::adaptive_card_body) em vez do
sample generico do adaptivecards.io usado como rascunho inicial
(adaptive-cards/generic-task-card/ no repo local, fora do versionamento).
"""
from __future__ import annotations

from typing import Any

EVENTOS_STATUS_REQUISITO: dict[str, dict[str, str]] = {
    'aprovado': {'estilo': 'good', 'icone': '✅'},
    'rejeitado': {'estilo': 'attention', 'icone': '⛔'},
    'prazo_vencendo': {'estilo': 'warning', 'icone': '⏰'},
    'concluido': {'estilo': 'good', 'icone': '🏁'},
    'bloqueado': {'estilo': 'attention', 'icone': '🚧'},
}


def construir_adaptive_card_status_requisito(
    *,
    evento: str,
    titulo: str,
    descricao: str,
    status_label: str = '',
    propriedades: list[dict[str, str]] | None = None,
    view_url: str = '',
    acao_titulo: str = 'Abrir no ReqSys',
) -> dict[str, Any]:
    """Monta um AdaptiveCard resolvido (sem placeholders de template) para um
    evento do ciclo de vida do requisito. Levanta ValueError se `evento` nao
    estiver em EVENTOS_STATUS_REQUISITO — o chamador decide se isso deve
    bloquear o envio ou cair para um card generico de fallback."""
    config = EVENTOS_STATUS_REQUISITO.get(evento)
    if config is None:
        raise ValueError(
            f"evento de status de requisito desconhecido: {evento!r} "
            f"(esperado um de {sorted(EVENTOS_STATUS_REQUISITO)})"
        )

    cabecalho_coluna_texto: list[dict[str, Any]] = [
        {'type': 'TextBlock', 'size': 'Medium', 'weight': 'Bolder', 'text': titulo, 'wrap': True},
    ]
    if status_label:
        cabecalho_coluna_texto.append(
            {'type': 'TextBlock', 'text': status_label, 'isSubtle': True, 'spacing': 'None', 'wrap': True}
        )

    corpo: list[dict[str, Any]] = [
        {
            'type': 'Container',
            'style': config['estilo'],
            'bleed': True,
            'items': [
                {
                    'type': 'ColumnSet',
                    'columns': [
                        {
                            'type': 'Column',
                            'width': 'auto',
                            'verticalContentAlignment': 'Center',
                            'items': [
                                {'type': 'TextBlock', 'text': config['icone'], 'size': 'ExtraLarge', 'weight': 'Bolder'}
                            ],
                        },
                        {
                            'type': 'Column',
                            'width': 'stretch',
                            'verticalContentAlignment': 'Center',
                            'items': cabecalho_coluna_texto,
                        },
                    ],
                }
            ],
        },
        {'type': 'TextBlock', 'text': descricao, 'wrap': True, 'spacing': 'Medium'},
    ]

    if propriedades:
        corpo.append(
            {
                'type': 'FactSet',
                'facts': [{'title': f"{item['key']}:", 'value': item['value']} for item in propriedades],
            }
        )

    card: dict[str, Any] = {
        '$schema': 'http://adaptivecards.io/schemas/adaptive-card.json',
        'type': 'AdaptiveCard',
        'version': '1.4',
        'body': corpo,
    }

    if view_url:
        card['actions'] = [{'type': 'Action.OpenUrl', 'title': acao_titulo, 'url': view_url}]

    return card
