# Requisitos — catálogo canônico no E2E de acessibilidade

## Objetivo

Impedir que o gate WCAG falhe por uma contagem exata obsoleta quando uma nova rota canônica é adicionada e realmente percorrida pelo teste.

## Requisitos

1. O E2E de acessibilidade deve carregar as rotas da fonte canônica `frontend/src/constants/rotasResponsivas.js`.
2. Todas as rotas autenticadas carregadas devem continuar sendo percorridas pelo Axe.
3. O catálogo não pode conter pares duplicados de caminho e `testId`.
4. A baseline de cobertura não pode regredir abaixo de 38 rotas autenticadas sem alteração explícita deste contrato.
5. Adicionar uma rota canônica não deve exigir editar uma igualdade numérica apenas para manter o CI verde.

## Evidência

A causa raiz foi introduzida quando `/service-cases/:caseId?` entrou no catálogo pela PR #1999, enquanto o teste de acessibilidade permaneceu com a expectativa fixa de 37 rotas.

## Critérios de aceite

- build frontend aprovado;
- Pre-PR Readiness com `READY_FOR_PR=passed` no HEAD exato;
- o E2E mantém varredura WCAG A/AA para cada rota autenticada;
- duplicidades continuam bloqueadas;
- nenhuma rota é removida ou ignorada para fazer o gate passar.
