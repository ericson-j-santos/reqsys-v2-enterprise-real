# Release Note — Governed PR Automation v1.0.0

## Resumo

Adiciona automação governada para validar PRs verdes e permitir merge controlado sem depender do auto-merge nativo do GitHub.

## Entregas

- Workflow manual `Governed PR Automation`.
- Modo `dry-run` padrão.
- Merge explícito somente com `execute_merge=true`.
- Label obrigatória `governed-merge-approved`.
- Validação dos principais gates de CI e governança.
- Squash merge com head SHA esperado.
- Runbook operacional.

## Benefício

Reduz espera operacional manual sem relaxar qualidade, governança ou segurança.

## Critérios de aceite

- Workflow disponível em GitHub Actions.
- Execução manual aceita `pr_number`, `execute_merge` e `required_label`.
- PR sem label obrigatória é bloqueado.
- PR draft é bloqueado.
- PR com CI pendente/vermelho é bloqueado.
- Merge só ocorre quando todos os gates estiverem verdes e o usuário autorizar explicitamente.

## Próximo incremento recomendado

Integrar o resultado da automação ao Operational Actions Center para exibir score, decisão e bloqueios em endpoint operacional.
