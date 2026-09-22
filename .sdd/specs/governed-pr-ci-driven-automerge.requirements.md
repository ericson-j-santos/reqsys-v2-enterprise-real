# Governed PR Automation — auto-merge CI-driven

## Objetivo
Executar o merge governado de Pull Requests do ReqSys por evento de CI, sem agendamento e sem depender de nova solicitação manual, quando o HEAD atual estiver integralmente verde e elegível.

## Requisitos
1. O gatilho automático deve ser a conclusão do workflow `Governed Merge Queue`, não `schedule`/cron.
2. Somente runs `success` originados de `pull_request` podem iniciar avaliação de merge.
3. O PR deve estar aberto, não-draft, com base `main`, `mergeable=true` e possuir **simultaneamente** as labels `merge-queue:eligible` e `governed-merge-approved`. CI verde ou elegibilidade da fila não constituem autorização de merge.
4. Todos os workflows obrigatórios definidos em `REQUIRED_WORKFLOWS` devem estar `completed/success` no HEAD exato.
5. O SHA do PR deve coincidir com o `head_sha` da execução da fila governada.
6. Imediatamente antes do merge, o PR e suas labels devem ser relidos; HEAD, `merge-queue:eligible` e `governed-merge-approved` devem permanecer válidos. Qualquer divergência bloqueia a mutação.
7. O merge deve usar `squash` e enviar o SHA esperado à API GitHub (`sha: triggerHeadSha`).
8. Mudança de SHA deve falhar fechado; o novo ciclo de `synchronize` deve reexecutar os gates antes de nova tentativa.
9. O workflow não pode executar deploy, promoção de ambiente, alteração de segredos ou permissões administrativas.
10. O caminho manual existente por `workflow_dispatch` deve permanecer disponível e inalterado para contingência governada.\n11. O caminho CI-driven nunca pode adicionar `governed-merge-approved`; essa label representa autorização explícita externa ao resultado de CI.

## Critérios de aceite
1. Teste contratual comprova gatilho `workflow_run` da fila governada e ausência de `schedule`.
2. Teste contratual comprova dupla validação do HEAD e merge com SHA esperado.
3. Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato e `behind_by=0`.
4. Após abertura da PR, todos os gates obrigatórios devem passar no novo SHA antes do merge.
5. O merge automático só ocorre depois da `Governed Merge Queue` verde **e** da presença de `governed-merge-approved`.\n6. Teste contratual comprova que a autorização explícita é revalidada imediatamente antes de `pulls.merge`.
