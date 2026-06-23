# Validação pós-PR #118 — workflow-only e deep review

## Contexto

O PR #118 introduziu a governança de fast review e o workflow `pr-scope-labeler.yml`.

## Evidência validada

- `.github/workflows/pr-scope-labeler.yml` existe na `main`.
- `docs/adr/ADR-0021-coderabbit-fast-review-governance.md` existe na `main`.
- `docs/governance/CODERABBIT_FAST_REVIEW_GUARDRAILS.md` existe na `main`.
- `docs/ci/CI_ACCELERATION_STRATEGY.md` existe na `main`.
- `docs/00_INDICE_CANONICO.md` referencia os novos artefatos.

## Correção incremental

A estratégia de CI foi ajustada para deixar explícito que mudanças em `.github/workflows/` continuam elegíveis a feedback rápido, mas devem permanecer classificadas como `security-critical` e `deep-review` por alterarem superfície de automação privilegiada.

## Bloqueios preservados

- CI completo verde continua obrigatório antes de qualquer avanço.
- Revisão concluída continua obrigatória.
- Autorização explícita continua obrigatória para ready/merge.
