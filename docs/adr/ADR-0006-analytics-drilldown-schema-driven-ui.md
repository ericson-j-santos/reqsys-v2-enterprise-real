# ADR-0006 — Analytics, Drill-down e Schema-Driven UI

Status: aceito
Data: 2026-06-20

## Contexto

O ReqSys deve transformar indicadores, cards, gráficos e listas em componentes analíticos acionáveis, permitindo navegar do resumo ao detalhe filtrado.

## Decisão

Adotar como padrão:

1. Todo indicador relevante deve avaliar possibilidade de drill-down.
2. O drill-down deve preservar contexto, filtros e origem do dado.
3. Telas com dados variáveis devem evoluir para `Schema-Driven UI`.
4. O backend deve poder retornar `schema + data` para reduzir acoplamento com nomes fixos de colunas.

## Fluxo analítico

```text
indicador → filtro contextual → analítico → detalhe → evidência/origem
```

## Consequências

- Melhor experiência para investigação operacional.
- Menor retrabalho em telas com estruturas variáveis.
- Mais rastreabilidade entre visão executiva e dados brutos.

## Critérios de aceite

- Cards e gráficos clicáveis quando houver analítico correspondente.
- Estado de filtro preservado.
- Layout responsivo em visão sintética e analítica.
- Metadados de campo documentados quando a tela for orientada a schema.
