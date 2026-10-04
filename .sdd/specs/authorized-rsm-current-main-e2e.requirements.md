# Gateway autorizado — E2E RSM no SHA corrente da main

## Objetivo

Permitir reexecutar o workflow existente de evidência RSM contra a `main` corrente por uma rota governada, sem branch, workflow, ambiente ou parâmetros arbitrários no comentário.

## Requisitos

1. O gateway deve aceitar somente o comando literal `/reqsys run rsm-service-case-e2e-current-main`.
2. O comando permanece restrito à issue #1705 e ao ator `ericson-j-santos`.
3. O workflow alvo deve ser fixo em `rsm-service-case-e2e.yml`.
4. A referência deve ser fixa em `main`.
5. Nenhum input livre deve ser aceito pelo comando.
6. O gateway deve capturar a `main` corrente e validar que o run despachado pertence ao mesmo SHA.
7. O workflow RSM continua responsável pelo E2E HTTP -> FastAPI -> PostgreSQL, leitura independente, testes direcionados e artifacts.
8. A rota não autoriza deploy, produção, segredo ou alteração administrativa.
9. Aceitação do dispatch não equivale a conclusão do E2E.

## Critérios de aceite

- teste de contrato confirma comando, workflow e ref exatos;
- o alvo não entra no tratamento de runner self-hosted, pois roda em GitHub-hosted;
- Pre-PR Readiness fica verde no HEAD exato e base atual;
- após merge, o run alvo deve executar no SHA exato da main e o job RSM-08 deve terminar verde com artifact presente.
