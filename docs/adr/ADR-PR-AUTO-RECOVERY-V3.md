# ADR — PR Auto Recovery Controlled v3

## Status

Proposed.

## Context

A v1 consolidou diagnóstico read-only. A v2 consolidou recovery assisted dry-run, com plano, allowlist e blocked files.

A v3 introduz abertura automática controlada de PR substituto em draft, condicionada a gates explícitos.

## Decision

Permitir criação automática de PR substituto somente quando todos os gates forem verdadeiros:

1. O PR original está aberto.
2. O PR original está `mergeable=false`.
3. O PR original não é draft abandonado sem CI recente.
4. O diff é composto somente por arquivos allowlisted.
5. Nenhum arquivo blocked está presente.
6. A branch substituta nasce da `main` atual.
7. O PR substituto nasce como draft.
8. O PR original recebe comentário de supersedência proposta.
9. O PR original não é fechado automaticamente.
10. Não há merge automático.

## Allowlist

- `docs/**`
- `frontend/**`
- `scripts/**`
- `.github/workflows/pr-*.yml`
- `.github/workflows/*quality*.yml`
- `.github/workflows/*governance*.yml`

## Blocklist

- `secrets/**`
- `infra/production/**`
- `terraform/prod/**`
- `.github/CODEOWNERS`
- `.github/workflows/*deploy*.yml`
- `.github/workflows/*release*.yml`
- `.github/workflows/*production*.yml`

## Explicit non-goals

- No auto-merge.
- No auto-close of original PR.
- No production deploy.
- No environment approval.
- No secret mutation.
- No branch protection mutation.

## Consequence

The system can prepare safe replacement PRs faster while preserving human review and merge control.
