# Branch Protection Enterprise Baseline

## Objetivo

Estabelecer a recomendação operacional final para alinhar o ReqSys Enterprise ao padrão ouro de entrega governada.

## Estado alvo

A branch `main` deve ser protegida por ruleset ou branch protection com os seguintes controles obrigatórios:

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
| Squash merge | Sim | Mantém histórico linear e rastreável |

## Checks mínimos recomendados

Os nomes exatos devem refletir os jobs existentes no GitHub Actions. Para este repositório, a linha base recomendada é:

- `Governança Padrão Ouro`
- `Governance Quality Gates`
- `CI — ReqSys v2 Enterprise`
- `CI Enterprise Fast`
- `Branch Protection Audit`

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
- Block force pushes.
- Do not allow bypassing the above settings.

## Merge policy

Manter apenas:

- Squash merge.

Desabilitar, quando possível:

- Merge commit.
- Rebase merge.

## Critérios de aceite

- Branch `main` aparece como protegida no GitHub.
- Warning `Repository has no branch protection rules` deixa de aparecer.
- PR sem CI verde não pode ser mergeado.
- Push direto na `main` é bloqueado.
- Alteração em área sensível exige CODEOWNER.
- Evidência do workflow `Branch Protection Audit` publicada como artifact.

## Limitação operacional registrada

A aplicação efetiva do ruleset depende de permissão administrativa no GitHub. Quando a automação conectada não expõe endpoint de rulesets/branch protection, este documento, o CODEOWNERS e o workflow de auditoria estabelecem a baseline versionável; a ativação final deve ser feita em Settings por usuário administrador.
