# Repository Governance Agent — sincronização de branches

## Objetivo

Eliminar o retrabalho recorrente causado por PRs que ficam atrás da `main` após outro merge, mantendo o merge governado existente como única rota de integração.

## Classificação

`hotfix`.

## Requisitos

1. A cada `push` na `main`, o agente deve inspecionar PRs abertas cuja base seja `main`.
2. O agente só pode atualizar branches pertencentes ao próprio repositório; forks externos devem ser ignorados.
3. PRs em draft, com conflito, mergeabilidade desconhecida ou cujo estado/SHA tenha mudado antes da mutação não podem ser atualizadas.
4. A decisão de atualização deve usar `behind_by > 0` em comparação com a `main` corrente.
5. A chamada de atualização deve enviar `expected_head_sha` igual ao HEAD relido imediatamente antes da mutação.
6. Após a chamada, o agente deve reler o PR e comprovar um novo HEAD com `behind_by=0`.
7. Ausência de confirmação deve falhar o job; código HTTP aceito isoladamente não é sucesso.
8. O fan-out máximo por avanço da `main` deve ser 3 PRs para evitar tempestade de CI.
9. O agente não pode executar merge, deploy, promoção, force-push, alteração de segredo ou branch protection.
10. O `Governed Merge Queue` e o `Governed PR Automation` existentes continuam responsáveis pela validação e pelo merge depois que os gates do novo HEAD ficarem verdes.
11. O `GITHUB_TOKEN` nativo do workflow deve permanecer estritamente read-only (`contents: read` e `pull-requests: read`) para as inspeções. A mutação `update-branch` deve usar token temporário da GitHub App governada `REQSYS_STACK_REBASE_APP_ID`/`REQSYS_STACK_REBASE_PRIVATE_KEY`, solicitando `pull-requests: write` e `contents: write`, pois o GitHub exige que uma GitHub App também possa escrever o conteúdo do repositório HEAD ao executar `update-branch`; não pode usar PAT nem fallback para `GITHUB_TOKEN`.
12. O self-sync de PR deve usar `pull_request_target`, executando a definição confiável da `main` e sem checkout/execução de código controlado pela branch do PR.
13. Execuções concorrentes de sincronização devem usar lane determinística e cancelar execução obsoleta.
14. Ausência da configuração da GitHub App ou incapacidade de emitir o escopo solicitado deve falhar fechado antes de qualquer mutação.
15. Antes de solicitar qualquer token de escrita, cada job deve fazer uma inspeção somente leitura com o token nativo para comprovar que existe mutação elegível. Se a PR atual já estiver com `behind_by=0`, ou se não houver PR elegível atrasada no fan-out global, a execução deve terminar como `no-op` sem emitir token da GitHub App.

## Controles negativos

- draft => não atualiza;
- fork externo => não atualiza;
- conflito => não atualiza;
- mergeabilidade desconhecida => não atualiza;
- HEAD mudou entre leitura e mutação => `stale_noop`;
- orçamento de 3 atualizações esgotado => `deferred`;
- uso do `GITHUB_TOKEN` para `update-branch` é inválido: o E2E mostrou HTTP 403 com escopo insuficiente e, depois da ampliação, SHAs criados pelo `github-actions[bot]` produziram workflows `action_required`;
- GitHub App ausente ou sem o escopo solicitado => falha antes da mutação;
- execução sem mutação elegível (`behind_by=0` no self-sync ou nenhuma PR elegível atrasada no fan-out) => não solicita token de escrita e não falha por permissão administrativa desnecessária;
- API aceita a atualização, mas `behind_by` não chega a zero => job falha;
- nenhum caminho do workflow chama API de merge.

## Critérios de aceite

- `tests/test_repository_governance_agent.py` verde;
- SDD Gate verde no HEAD final;
- CI do PR verde no HEAD atual;
- `GITHUB_TOKEN` nativo continua read-only;
- token de mutação é emitido pela GitHub App já governada com `pull-requests: write` e `contents: write`, sem PAT/fallback;
- token de escrita só é solicitado depois de uma leitura `contents: read` + `pull-requests: read` comprovar `behind_by > 0` em uma PR elegível;
- após merge deste hotfix, o `push` da própria `main` dispara o agente;
- se houver PR segura atrasada, leitura independente deve observar novo HEAD e `behind_by=0`;
- o novo SHA produzido pela GitHub App deve disparar workflows de PR normalmente, sem `action_required`;
- PR com gate pendente pode ter branch sincronizada, mas não pode ser mergeada por este agente;
- leitura independente confirma que nenhuma PR foi mergeada pelo `Repository Governance Agent`;
- nenhuma ação de deploy/promoção é executada.
