# Merge Queue Reliability Metrics

## Objetivo

Instrumentar, sem criar gate, a confiabilidade do caminho de Merge Queue nativa e do estado imediatamente posterior ao merge.

## Escopo

A implementação reutiliza o `CI Lead Time Analytics` e sua amostra de PRs. Não habilita Merge Queue, não altera ruleset, não executa merge e não modifica thresholds de CI.

## Requisitos

1. Um canário só pode ser considerado observado quando existir workflow run real com `event=merge_group` associado a PR.
2. Ausência de `merge_group` deve permanecer explícita como `available=false` e `canary_e2e_observed=false`.
3. Tentativas da fila devem ser deduplicadas por HEAD SHA de `merge_group`, evitando contar vários workflows do mesmo candidato como tentativas distintas.
4. Registrar P50/P95 de `created_at -> run_started_at` dos workflows `merge_group`, com semântica explícita de espera do GitHub Actions.
5. Registrar PR verde nos workflows bloqueantes que posteriormente apresente falha em `merge_group`.
6. Registrar falhas da fila por workflow/conclusão observada.
7. Registrar requeue quando o mesmo PR estiver associado a mais de um HEAD SHA de `merge_group`.
8. Para falha pós-merge, consultar somente o `merge_commit_sha` exato de PRs da amostra que tenham sido mergeadas dentro da janela.
9. Falha pós-merge é sinal observacional e não deve ser apresentada como prova causal da mudança.
10. Workflow pós-merge com conclusão `cancelled` deve permanecer observável, mas não pode incrementar `post_merge_failure_runs` nem `post_merge_failed_pr_count`.
11. Se a paginação global de runs não cobrir a janela ampliada de PRs, usar o fallback bounded por PR recente/commit/head_sha em vez de falhar antes da contingência.
12. Todas as métricas permanecem `report-only` e `creates_gate=false`.

## Controles negativos

- Nenhum `merge_group` observado não pode produzir canário aprovado.
- Workflow `push` de SHA diferente do `merge_commit_sha` da PR não participa da métrica pós-merge.
- Vários workflows no mesmo HEAD `merge_group` não podem inflar `queue_attempts`.
- Workflow pós-merge cancelado deve ser reportado separadamente e não pode ser rotulado como falha.

## Critérios de aceite

- Teste positivo detecta PR verde com falha de fila e requeue.
- Teste negativo mantém canário não observado quando a amostra não contém `merge_group`.
- Teste de coleta prova consulta pós-merge pelo SHA exato.
- Teste negativo prova que `cancelled` pós-merge fica visível sem ser contado como falha.
- Teste prova que paginação global incompleta aciona `recent_prs_fallback` bounded.
- Schema documenta `merge_queue_reliability`.
- `CI Lead Time Analytics` continua report-only.
- Pre-PR Readiness fica verde no HEAD final com `behind_by=0`.
