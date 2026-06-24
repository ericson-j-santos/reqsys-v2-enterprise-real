# ADR — PR Auto Recovery Assisted v2

## Status

Accepted.

## Context

A v1 do PR Auto Recovery Diagnostics já identifica:

- PRs com `mergeable=false`;
- falhas críticas de CI;
- workflows travados;
- ausência de evidência operacional.

Ainda existe ação manual repetitiva para:

- decidir criação de branch limpa;
- determinar arquivos seguros para reaplicação;
- padronizar recovery plan.

## Decisão

A v2 introduz modo `assisted-dry-run`.

Ela:

- cria plano de recovery;
- gera allowlist de arquivos reaplicáveis;
- identifica risco operacional;
- simula criação de PR substituto;
- gera artifacts operacionais.

Ela NÃO:

- cria PR real;
- cria branch real;
- fecha PR;
- faz merge;
- altera produção;
- altera branch protection;
- altera secrets.

## Allowlist inicial

Arquivos seguros:

- `docs/**`
- `frontend/**`
- `scripts/**`
- `.github/workflows/**` limitados a workflows permitidos.

## Bloqueios obrigatórios

Bloquear recovery automático quando houver:

- `infra/production/**`
- `terraform/prod/**`
- `secrets/**`
- `.github/CODEOWNERS`
- branch protection
- environments protegidos
- deploy workflows críticos

## Resultado esperado

Reduzir recuperação operacional de conflito para poucos minutos mantendo governança explícita.
