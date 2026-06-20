# 2026-06-20 — Hotfix — Governança CodeRabbit

## Contexto

Durante a validação pós-merge da frente REQSYS-OPER-005, o CodeRabbit indicou que a chave `custom_instructions` em `.coderabbit.yaml` não é reconhecida pelo schema de configuração.

## Decisão

Substituir `custom_instructions` por chaves reconhecidas na configuração atual do CodeRabbit:

- `tone_instructions` para tom geral.
- `reviews.high_level_summary_instructions` para orientar resumo executivo.
- `reviews.path_instructions` para orientar revisões por caminho.
- `reviews.pre_merge_checks.custom_checks` para checks de governança.

## Resultado esperado

- Remover warning de chave não reconhecida.
- Manter relatório de monitoramento do PR em português do Brasil.
- Manter tabela de resultado da revisão.
- Reforçar CI verde como condição necessária para prontidão.
- Evitar auto-review em PRs draft para reduzir ruído e rate limit.

## Governança

Este hotfix não altera código produtivo da aplicação. O PR deve permanecer em draft até validação de CI e confirmação de que o CodeRabbit não reporta mais `custom_instructions` como chave inválida.

Refs: REQSYS-OPER-005, PR #50.
