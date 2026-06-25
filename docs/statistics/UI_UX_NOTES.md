# UI/UX — Aba Estatísticas v1

## Diretrizes aplicadas

- Página responsiva baseada em grid Vuetify.
- Cards executivos no topo para leitura rápida.
- Filtros por categoria, fonte e estado atual.
- Cards analíticos individuais com metadados completos.
- Tabela consolidada para visão operacional.
- Diferenciação explícita entre fonte interna e externa.
- Uso de chips visuais para estado e guard rails.
- Drill-down navegável por indicador, acessível por botão nos cards e por linha clicável/teclado na tabela.

## Acessibilidade inicial

- Título principal com `aria-labelledby`.
- Hierarquia visual clara.
- Conteúdo tabular para leitura analítica.
- Evita depender exclusivamente de cor: estados também aparecem como texto.
- Ação de drill-down possui `aria-label`, foco por teclado e abertura por `Enter`/`Space` na tabela.

## Drill-down operacional

O drill-down por indicador consolida:

- valor atual, estado atual, estado alvo e tendência;
- fonte, origem, confiabilidade, data de coleta e versão do conector;
- fórmula documentada;
- evidências;
- pendências;
- violações de guard rails;
- próxima ação objetiva;
- trilha de auditoria navegável baseada em indicador, fonte e estado.

## Limites evidenciados

- O drill-down usa o contrato já carregado pela aba `/estatisticas`.
- Não promove estado atual para estado alvo.
- Não cria fonte externa real quando a origem ainda é fallback ou registry pendente.
- Não altera ambiente produtivo.

## Melhorias futuras

- Adicionar exportação CSV/JSON.
- Adicionar links diretos para evidências versionadas.
- Adicionar gráficos de tendência após fonte histórica real.
- Conectar o drill-down a rotas dedicadas quando houver backend histórico por indicador.
