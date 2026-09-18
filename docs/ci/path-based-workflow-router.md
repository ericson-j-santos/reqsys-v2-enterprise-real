# Path-Based Workflow Router

## Objetivo

Reduzir a quantidade de workflows disparados em PRs pequenos sem remover governança, segurança ou rastreabilidade.

Este incremento aplica filtros por caminho em workflows analíticos/advisory que não precisam rodar para alterações puramente documentais ou não correlacionadas.

## Workflows ajustados

| Workflow | Motivo | Política |
|---|---|---|
| `Runtime Risk Scoring` | Analisa risco de runtime/segurança/infra | Roda apenas para backend, frontend, scripts, config, infra, workflows e docs operacionais |
| `PR Quality Review` | Revisão governada de PR | Roda apenas para código, testes, workflows, config, docs técnicas/operacionais e manifests de pacote |
| `Predictive Regression Guard` | Gate preditivo advisory | Roda apenas quando há risco real de regressão operacional |

## Guardrail

O workflow `ReqSys Required Fast Gate` permanece sem redução por path e continua sendo o candidato a check obrigatório principal.

## Efeito esperado

- Menos workflows em PRs pequenos.
- Menos fila no GitHub Actions.
- Menos falsos bloqueios em mudanças documentais simples.
- Preservação de execução manual por `workflow_dispatch` quando uma análise sob demanda for necessária.

## Rollback

Remover os blocos `paths:` adicionados nos workflows alterados.
