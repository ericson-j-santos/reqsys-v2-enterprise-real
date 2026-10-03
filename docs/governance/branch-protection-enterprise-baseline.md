# Branch Protection Enterprise Baseline

## Objetivo

Estabelecer a recomendação operacional final para alinhar o ReqSys Enterprise ao padrão ouro de entrega governada.

## Estado alvo

A branch `main` deve ser protegida por ruleset ou branch protection com os seguintes controles obrigatórios. Esta seção é a fonte canônica para revisar e ajustar `required status checks`, `required approvals`, `merge queue`, `auto-merge` e `bypass permissions` antes de confirmar a proteção final da `main`:

| Controle | Obrigatório | Motivo |
|---|---:|---|
| Pull request antes do merge | Sim | Impede alteração direta em produção |
| Aprovação mínima | Sim | Garante revisão humana |
| CODEOWNERS | Sim | Exige revisão por responsável técnico |
| Dismiss stale approvals | Sim | Invalida aprovação após novo commit |
| Status checks obrigatórios | Sim | Impede merge com CI quebrado |
| Branch atualizada antes do merge | Sim | Reduz regressão por base defasada |
| Conversas resolvidas | Sim | Impede pendência não tratada |
| Bloqueio de force push | Sim | Preserva histórico auditável |
| Bloqueio de deleção | Sim | Evita perda da branch principal |
| Sem bypass | Sim | Evita exceções silenciosas |
| Merge queue governada | Sim | Garante integração temporária contra `main` antes do merge |
| Auto-merge nativo | Sim, condicionado | Permitido somente quando PR, aprovações e checks obrigatórios estiverem verdes |
| Squash merge | Sim | Mantém histórico linear e rastreável |

## Required status checks

Required status check no GitHub é o **check run name**, que corresponde ao `name` do job (ou ao job id quando o job não declara `name`) — nunca ao nome do workflow. Configurar nome de workflow como contexto obrigatório trava o PR em `Expected — Waiting for status to be reported`, porque nenhum check com aquele nome é publicado.

Linha base recomendada (contextos comprovados por `scripts/build_required_checks_stale_inventory.py`, todos `active` em PR para `main`):

| Contexto obrigatório (check run name) | Workflow produtor | Job |
| --- | --- | --- |
| `Required Fast Gate` | `ReqSys Required Fast Gate` | `required-fast-gate` |
| `CI Router Result` | `CI — ReqSys v2 Enterprise` | `ci-result` (`if: always()`) |
| `Sumario CI Enterprise Fast` | `CI Enterprise Fast` | `ci-fast-summary` (`if: always()`) |
| `Validar artefatos de governança` | `Governança Padrão Ouro` | `validar-governanca` |
| `governance-validation` | `Governance Quality Gates` | `governance-validation` (job sem `name`) |
| `Security Baseline` | `Security Baseline Gate` | `security-baseline` |
| `Auditar proteção enterprise da branch` | `Branch Protection Audit` | `audit` |
| `Gate de merge governado` | `Governed Merge Queue` | `merge-queue-gate` (`if: always()`) |

Nomes de workflow (`Governança Padrão Ouro`, `Governance Quality Gates`, `CI — ReqSys v2 Enterprise`, `CI Enterprise Fast`, `Branch Protection Audit`, `Governed Merge Queue`) permanecem válidos como referência de workflow, mas **não** devem ser usados como contexto obrigatório. A decisão de renomear cada um para o check run name real está registrada em `config/required-checks-inventory-policy.json` e auditada por `docs/governance/required-checks-stale-inventory.md`.

Checks com filtro de caminhos, job matricial, `if` condicional sem `always()` ou trigger fora de `pull_request` podem permanecer opcionais, porque não materializam de forma determinística em todo PR. Antes de alterar a proteção, rodar o inventário e tratar todo contexto classificado como `stale`, `renamed_candidate`, `workflow_name_mismatch`, `conditional_risk` ou `not_pr_triggered`.

## Required approvals

Configurar aprovação humana mínima e revisão por ownership:

- Require approvals: `1` ou mais.
- Require review from Code Owners: habilitado.
- Dismiss stale pull request approvals when new commits are pushed: habilitado.
- Require conversation resolution before merging: habilitado.
- Não permitir aprovação como único gate quando required status checks estiverem pendentes ou falhos.

## Merge queue

A fila governada deve permanecer aderente ao runbook `docs/runbooks/governed-merge-queue.md`:

- Exigir validação isolada do PR.
- Exigir integração temporária contra `main`.
- Exigir smoke runtime em modo reportável antes de marcar elegibilidade.
- Usar a label `merge-queue:eligible` somente como sinal técnico, nunca como bypass de CI ou revisão.
- Não promover PR com alteração crítica em contratos, secrets, branch protection ou bootstrap global sem decisão registrada.

## Auto-merge

Manter `allow_auto_merge=true` no repositório para PRs que já estejam elegíveis, mas aplicar as restrições abaixo:

- Auto-merge só pode ser habilitado por PR após required approvals, CODEOWNERS e required status checks.
- Auto-merge nativo não substitui merge queue governada nem evidência do CI.
- Se `allow_auto_merge=false`, registrar gap operacional e seguir com Governed PR Automation ou merge manual após todos os gates.

## Bypass permissions

A política final da `main` deve bloquear bypass silencioso:

- Do not allow bypassing the above settings: habilitado.
- Bypass list: vazia, salvo break-glass formalmente documentado.
- Administradores e GitHub Apps também devem seguir os controles quando a interface permitir.
- Qualquer exceção temporária deve registrar motivo, aprovador, janela, rollback e evidência pós-uso.

## Ruleset recomendado

Configurar em:

```text
Settings > Rules > Rulesets > New ruleset > New branch ruleset
```

### Target

```text
Default branch
```

ou explicitamente:

```text
main
```

### Rules

Ativar:

- Restrict deletions.
- Require a pull request before merging.
- Require approvals: `1`.
- Dismiss stale pull request approvals when new commits are pushed.
- Require review from Code Owners.
- Require status checks to pass.
- Require branches to be up to date before merging.
- Require conversation resolution before merging.
- Require merge queue, quando disponível para o plano/repositório; caso contrário, manter o workflow `Governed Merge Queue` como gate obrigatório de equivalência operacional.
- Block force pushes.
- Do not allow bypassing the above settings.
- Manter bypass permissions vazias, salvo break-glass documentado.

## Merge policy

Manter apenas:

- Squash merge.

Desabilitar, quando possível:

- Merge commit.
- Rebase merge.

## Checklist de confirmação final da `main`

Antes de declarar a proteção final aplicada, revisar em `Settings > Rules > Rulesets` ou `Settings > Branches > Branch protection rules`:

1. Required status checks contém a linha base deste documento e não referencia checks inexistentes.
2. Required approvals exige pelo menos `1` aprovação, CODEOWNERS e dismiss stale approvals.
3. Merge queue está habilitada no GitHub ou coberta pelo workflow `Governed Merge Queue` como gate obrigatório.
4. Auto-merge está habilitado no repositório, mas condicionado a PR elegível e checks verdes.
5. Bypass permissions está vazio ou contém apenas break-glass temporário documentado.
6. Proteções contra force push e deleção estão ativas para `main`.

## Critérios de aceite

- Branch `main` aparece como protegida no GitHub.
- Warning `Repository has no branch protection rules` deixa de aparecer.
- PR sem CI verde não pode ser mergeado.
- Push direto na `main` é bloqueado.
- Alteração em área sensível exige CODEOWNER.
- Evidência do workflow `Branch Protection Audit` publicada como artifact.

## Limitação operacional registrada

A aplicação efetiva do ruleset depende de permissão administrativa no GitHub. Quando a automação conectada não expõe endpoint de rulesets/branch protection, este documento, o CODEOWNERS e o workflow de auditoria estabelecem a baseline versionável; a ativação final deve ser feita em Settings por usuário administrador.
