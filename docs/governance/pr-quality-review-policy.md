# Política — PR Quality Review

## Objetivo

Garantir revisão automatizada objetiva sem dependência de GitHub App externo.

## Regras

- `critical` bloqueia.
- `warning` evidencia risco, mas não bloqueia por padrão.
- `ok` libera apenas o gate específico do PR Quality Review.
- Checks obrigatórios, branch protection e revisão humana continuam prevalecendo.

## Escopo fora

- Não faz merge automático.
- Não promove produção.
- Não altera secrets, environments ou branch protection.
