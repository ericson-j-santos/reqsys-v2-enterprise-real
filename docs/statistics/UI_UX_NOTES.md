# UI/UX — Aba Estatísticas v1

## Diretrizes aplicadas

- Página responsiva baseada em grid Vuetify.
- Cards executivos no topo para leitura rápida.
- Filtros por categoria, fonte e estado atual.
- Cards analíticos individuais com metadados completos.
- Tabela consolidada para visão operacional.
- Diferenciação explícita entre fonte interna e externa.
- Uso de chips visuais para estado e guard rails.

## Acessibilidade inicial

- Título principal com `aria-labelledby`.
- Hierarquia visual clara.
- Conteúdo tabular para leitura analítica.
- Evita depender exclusivamente de cor: estados também aparecem como texto.

## Melhorias futuras

- Adicionar drill-down modal por indicador.
- Adicionar exportação CSV/JSON.
- Adicionar links diretos para evidências versionadas.
- Adicionar gráficos de tendência após fonte histórica real.
