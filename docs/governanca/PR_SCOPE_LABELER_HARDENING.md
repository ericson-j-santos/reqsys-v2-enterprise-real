# Reconciliação do PR #119 — PR Scope Labeler e CodeRabbit

## Objetivo original

Reduzir o risco do rotulador de PR e diminuir dependência/ruído do CodeRabbit.

## Estado canônico atual

A `main` evoluiu além da implementação histórica:

- `PR Scope Labeler` usa `pull_request`, não `pull_request_target`;
- o labeler opera em modo read-only/fail-safe;
- não adiciona nem remove labels;
- não possui `issues: write`;
- CodeRabbit está desativado operacionalmente;
- a revisão canônica é `PR Quality Review`.

## Decisão

Não restaurar a configuração antiga do CodeRabbit nem a mutação de labels do PR #119.

O objetivo do PR é preservado por teste preventivo que bloqueia reintrodução de:

- `pull_request_target`;
- permissão `issues: write` no labeler;
- chamadas de mutação de labels;
- configuração ativa de auto-review do CodeRabbit.

## Resultado

A recuperação elimina o estado `changed_files=0` sem criar diff artificial: o novo diff documenta e testa a decisão canônica atual.
