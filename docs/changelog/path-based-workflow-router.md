# Path-Based Workflow Router

## Contexto

As verificações de PR estavam demorando porque múltiplos workflows analíticos e report-only eram disparados mesmo em mudanças pequenas.

## Entrega

- Adicionado roteamento por `paths` nos workflows:
  - `Runtime Risk Scoring`;
  - `PR Quality Review`;
  - `Predictive Regression Guard`.
- Mantido `ReqSys Required Fast Gate` sem filtro por path para preservar o caminho crítico obrigatório.
- Adicionado validador dedicado:
  - `scripts/validate_path_based_workflow_router.py`.
- Adicionado workflow de validação do roteamento:
  - `.github/workflows/path-based-workflow-router-validation.yml`.

## Impacto esperado

- Redução de workflows disparados em PRs pequenos.
- Menos fila em GitHub Actions.
- Menor ruído operacional.
- Preservação de execução manual por `workflow_dispatch`.

## Rollback

Remover os blocos `paths:` adicionados e excluir:

- `scripts/validate_path_based_workflow_router.py`;
- `.github/workflows/path-based-workflow-router-validation.yml`;
- `docs/ci/path-based-workflow-router.md`.
