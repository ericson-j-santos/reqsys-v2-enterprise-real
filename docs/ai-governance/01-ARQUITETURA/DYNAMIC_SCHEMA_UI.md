# Dynamic Schema UI

Codigo: AI-GOV-ARCH-002

## Decisao

Interfaces devem suportar renderizacao orientada por schema quando houver dados variaveis.

## Padrao recomendado

O backend pode retornar:

- schema
- dados
- metadados de coluna
- permissoes
- filtros
- mascaras
- regras de ordenacao

O frontend renderiza tabelas, cards, detalhes e filtros sem depender rigidamente de nomes fixos de colunas.

## Aplicacao no ReqSys

Aplicar em paineis analiticos, dashboards, consultas dinamicas e detalhamentos de informacoes.

## Referencias cruzadas

- docs/ai-governance/03-FRONTEND/ANALYTICS_DRILLDOWN.md
- docs/ai-governance/09-CHECKLISTS/GOLD_STANDARD.md