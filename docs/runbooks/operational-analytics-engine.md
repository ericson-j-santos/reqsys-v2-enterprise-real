# Operational Analytics & Trend Engine

## Objetivo

Evoluir a governança operacional de estado atual para leitura analítica de tendência, estabilidade e maturidade dos workflows.

## Escopo

O engine:

- lê runs recentes do GitHub Actions;
- calcula taxa de sucesso;
- calcula taxa de instabilidade;
- identifica tendência operacional;
- gera heatmap por workflow;
- calcula duração média por workflow;
- publica JSON, Markdown e dashboard HTML.

## Artifact

Artifact esperado:

`operational-analytics-evidence`

Conteúdo:

- `operational-analytics.json`
- `summary.md`
- `dashboard.html`

## Indicadores

| Indicador | Descrição |
|---|---|
| `success_rate` | Percentual de runs verdes |
| `instability_rate` | Percentual de runs amarelos/vermelhos |
| `trend` | Tendência operacional consolidada |
| `workflow_stats` | Heatmap por workflow |
| `avg_duration_seconds` | Duração média por workflow |

## Tendências

| Tendência | Significado |
|---|---|
| `estavel` | Alta taxa de sucesso e sem falhas críticas |
| `observacao` | Existem runs pendentes |
| `atenção` | Sucesso abaixo do limiar esperado |
| `regressao` | Existem falhas críticas recentes |

## Guard rails

Este workflow não:

- executa rerun;
- faz merge;
- faz deploy;
- altera produção;
- altera secrets;
- altera branch protection;
- executa auto-fix.

## Uso operacional

1. Executar `Operational Analytics Engine`.
2. Baixar artifact `operational-analytics-evidence`.
3. Abrir `dashboard.html`.
4. Validar tendência, workflows instáveis e taxa de sucesso.

## Links

- Actions: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions
