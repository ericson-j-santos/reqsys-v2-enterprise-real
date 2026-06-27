# Live Operational Dashboard Foundation

## Objetivo

Consolidar uma arquitetura viva para o ReqSys baseada em:

- visualização operacional integrada;
- analytics histórico;
- dashboard vivo consolidado;
- experiência operacional navegável.

## Fontes integradas

| Fonte | Tipo | Estado |
|---|---|---|
| runtime health | runtime | ativo |
| CI lead time analytics | artifact analytics | ativo |
| burndown executivo | governança | ativo |
| runtime risk scoring | analytics | ativo |
| PR evidence gate | evidência operacional | ativo |

## Camadas da arquitetura

```text
GitHub Actions
  -> artifacts analytics
  -> contracts schema-driven
  -> runtime governance
  -> executive burndown
  -> operational dashboard
```

## KPIs mínimos do dashboard

- success rate;
- failure rate;
- lead time médio;
- P50;
- P95;
- max lead time;
- top bottlenecks;
- runtime health;
- governance score;
- production readiness.

## Drill-down obrigatório

Cada KPI deve permitir:

- abrir workflow relacionado;
- abrir PR relacionado;
- abrir artifact relacionado;
- abrir risco operacional relacionado;
- abrir timeline histórica.

## Histórico operacional

O dashboard deve suportar:

- snapshots versionados;
- tendência temporal;
- regressão operacional;
- comparação antes/depois;
- baseline histórico de incidentes.

## Estado atual consolidado

| Dimensão | Maturidade |
|---|---:|
| CI/CD | 90% |
| Governança | 91% |
| Observabilidade | 88% |
| Analytics operacional | 84% |
| Runtime governance | 87% |
| Dashboard vivo | 68% |

## Próximas evoluções

1. Publicar dashboard HTML navegável.
2. Consumir artifacts automaticamente.
3. Adicionar timeline histórica persistente.
4. Integrar runtime graph navegável.
5. Publicar analytics executivo automático.
