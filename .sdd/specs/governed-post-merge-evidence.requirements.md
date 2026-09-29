# Governed exact-SHA post-merge evidence materialization

## Objetivo

Eliminar falso verde após merge governado executado com `GITHUB_TOKEN`, materializando explicitamente os workflows obrigatórios no `merge_sha` real sem PAT, custo adicional ou relaxamento de gates.

## Requisitos

1. Os dois caminhos de merge do `Governed PR Automation` devem emitir `repository_dispatch` com `pr_number`, `head_sha` e `merge_sha`.
2. O `Actions Dispatcher — ReqSys` existente deve consumir o evento, mantendo crescimento líquido zero em `.github/workflows`.
3. A materialização deve validar que a PR está mergeada e que `merge_commit_sha` e HEAD correspondem ao payload.
4. Uma branch temporária determinística deve apontar exatamente para o `merge_sha` somente durante a materialização.
5. `CI — ReqSys v2 Enterprise`, `Governance Quality Gates` e `Governança Padrão Ouro` devem ser disparados por `workflow_dispatch` na ref temporária quando ainda não houver execução para o mesmo SHA.
6. Replay do mesmo `merge_sha` não deve duplicar workflows já materializados; execução anterior falha deve permanecer fail-closed.
7. Após os três workflows verdes, `Main Post-Merge Validation` deve executar com `commit_sha=merge_sha`.
8. `Main Post-Merge Validation` permanece report-only em `push` e `schedule`, mas deve falhar fechado quando acionado por `workflow_dispatch` e o gate interno não estiver `passed`.
9. A ref temporária deve ser removida ao final somente se ainda apontar para o SHA esperado.
10. O dispatcher deve oferecer recuperação manual por `mode=post-merge` sem duplicar o caminho automático.
11. Todas as Actions externas tocadas devem estar pinadas por SHA completo.
12. Nenhum deploy, promoção, segredo novo, PAT, force-push ou escrita direta em `main` pertence a este incremento.

## Controles negativos

- SHA inválido, PR não mergeada, merge SHA divergente ou HEAD divergente bloqueiam antes do dispatch.
- Ref temporária existente em SHA diferente bloqueia sem sobrescrever.
- Workflow obrigatório existente com conclusão não verde bloqueia replay sem criar duplicata.
- Timeout de materialização falha fechado.
- `workflow_dispatch` do Main Post-Merge Validation com evidência incompleta termina em failure.
- Limpeza não remove ref cujo SHA mudou durante a execução.

## Critérios de aceite

- `tests/test_governed_post_merge_materializer_workflow.py` verde.
- `tests/test_governed_pr_automation_dispatch_contract.py` verde.
- `tests/test_main_post_merge_actions_discovery_guard.py` verde.
- Pre-PR Readiness verde no HEAD final e `behind_by=0`.
- `workflow:surface-budget` verde com crescimento líquido de workflows igual a zero.
- `workflow:action-immutability` verde para todos os workflows alterados.
- Teste pós-merge posterior comprova os três workflows obrigatórios e o Main Post-Merge Validation no mesmo `merge_sha`.
- Replay do mesmo `merge_sha` não cria novas execuções quando evidência terminal válida já existe.
