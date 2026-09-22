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
11. O workflow deve usar `contents: write` e `pull-requests: write`, menor combinação comprovada pelo E2E para a API `update-branch`; não pode receber `actions: write`, `issues: write` ou permissão administrativa.
12. Execuções concorrentes de sincronização devem compartilhar uma única lane e cancelar execução obsoleta.

## Controles negativos

- draft => não atualiza;
- fork externo => não atualiza;
- conflito => não atualiza;
- mergeabilidade desconhecida => não atualiza;
- HEAD mudou entre leitura e mutação => `stale_noop`;
- orçamento de 3 atualizações esgotado => `deferred`;
- token sem permissão de conteúdo para `update-branch` => falha explícita;\n- API aceita a atualização, mas `behind_by` não chega a zero => job falha;
- nenhum caminho do workflow chama API de merge.

## Critérios de aceite

- `tests/test_repository_governance_agent.py` verde;\n- controle E2E comprova que `contents: read` era insuficiente (HTTP 403) e a permissão corrigida permite a atualização sem ampliar para outras famílias;
- CI do PR verde no HEAD atual;
- após merge deste hotfix, o `push` da própria `main` dispara o agente;
- ao menos uma PR previamente atrasada deve ter HEAD alterado e `behind_by=0`, se existir candidata segura;
- PR com gate pendente pode ter branch sincronizada, mas não pode ser mergeada por este agente;
- leitura independente confirma que nenhuma PR foi mergeada por `Repository Governance Agent`;
- nenhuma ação de deploy/promoção é executada.
