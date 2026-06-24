# PR Auto Recovery Pipeline

## Objetivo

Detectar PRs abertos que precisam de intervenção operacional antes do merge, priorizando bloqueios críticos:

- `mergeable=false`;
- CI vermelho em workflows críticos;
- workflows críticos pendentes;
- PR draft com CI verde aguardando decisão;
- ausência de runs críticos no head atual.

## Modo operacional v1

A versão inicial é somente diagnóstico.

Ela não:

- cria branch;
- abre PR substituto;
- fecha PR antigo;
- faz merge;
- aprova review;
- altera branch protection;
- altera secrets;
- executa deploy.

## Artifact

Artifact esperado:

`pr-auto-recovery-diagnostics`

Conteúdo:

- `pr-auto-recovery.json`;
- `summary.md`.

## Severidade

| Severidade | Situação | Ação recomendada |
|---|---|---|
| P0 | `mergeable=false` | Criar substituto limpo manualmente ou via v2 governada |
| P0 | workflow crítico falho | Corrigir causa raiz ou reexecutar failed jobs |
| P1 | workflow crítico pendente | Revalidar depois da conclusão |
| P1 | draft | Tirar de draft após validação do dono |
| P2 | merge candidate | Prosseguir conforme política de review |

## Workflows críticos monitorados

- CI — ReqSys v2 Enterprise
- CI Enterprise Fast
- Governance Quality Gates
- Governança Padrão Ouro
- PR Conflict Guard
- PR Evidence Gate
- Branch Protection Audit
- PR CI Watch

## Evolução v2 recomendada

A v2 pode criar PR substituto automaticamente, mas somente se todos estes gates forem atendidos:

1. PR original está `mergeable=false`.
2. PR original não altera arquivos bloqueados de produção.
3. Diff está abaixo do limite de risco configurado.
4. Não há deploy, secrets, branch protection ou environment approval no escopo.
5. A branch substituta é criada a partir da `main` atual.
6. O PR substituto nasce em draft.
7. O PR antigo recebe comentário de supersedência, mas não é fechado automaticamente.

## Decisão de segurança

A v1 foi mantida read-only para reduzir risco operacional. O objetivo é padronizar evidência e decisão antes de automatizar mutações.
