# Workflow Dashboard

## Objetivo

Gerar um dashboard HTML autocontido com leitura executiva dos workflows criticos do ReqSys.

## Escopo

O dashboard:

- consulta runs recentes da branch `main`;
- calcula taxa de sucesso dos workflows criticos;
- lista falhas, pendencias e workflows ausentes na janela recente;
- gera HTML autocontido;
- gera JSON de resumo;
- publica artifact `workflow-dashboard`.

## Fora de escopo

Este workflow nao:

- executa deploy;
- altera producao;
- dispara outros workflows;
- altera secrets;
- faz merge automatico;
- altera branch protection.

## Artifact

Artifact esperado:

`workflow-dashboard`

Conteudo:

- `workflow-dashboard.html`
- `workflow-dashboard.json`

## Indicadores

| Indicador | Descricao |
|---|---|
| Runs recentes | Quantidade de runs coletados na janela |
| Runs criticos | Runs pertencentes aos workflows monitorados |
| Taxa de sucesso | Percentual de runs criticos com conclusao `success` |
| Falhas | Runs criticos com `failure`, `cancelled`, `timed_out` ou `action_required` |
| Pendentes | Runs criticos ainda nao completados |
| Ausentes | Workflows criticos nao encontrados na janela recente |

## Workflows criticos

- CI — ReqSys v2 Enterprise
- CI Enterprise Fast
- Fast CI - Operational Guardrails
- Governance Quality Gates
- Branch Protection Audit
- PR Conflict Guard
- Main Smoke CI
- Main Operational Health
- Workflow Command Center

## Decisao operacional

| Estado | Decisao |
|---|---|
| Verde | Continuar incrementos |
| Atencao | Verificar falhas/pendencias antes de novos merges |
| Ausentes na janela | Executar manualmente se forem evidencias obrigatorias |

## Links

- Actions: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions
