# Desktop Runtime Dedicated Runner Bridge — Requirements

## Objetivo

Eliminar a dependência circular em que o runner dedicado do Desktop precisa estar online para executar o próprio self-heal.

## Estado evidenciado

- O runner legado ReqSys `DESKTOP-PDQK954` é a rota externa já comprovada para recuperação do host.
- O runner dedicado do repositório `desktop-pc24x7-runtime` está offline e o smoke da PR #17 permanece queued.
- A branch histórica `ops/bootstrap-desktop-runtime-runner-20260923` está obsoleta e usava execução direta/credencial inadequada.
- O incremento atual é `consolidate`, permitido pelo gate operacional atual.

## Requisitos

1. Executar somente no runner legado com labels `self-hosted, Windows, X64, pc24x7, reqsys-dev`.
2. Fixar o código do Desktop runtime no SHA exato `05f9c63253f7da1eb73d88db5494a98471f0df2e`.
3. Fixar as regras operacionais no SHA `ac2297988651f41ab03469808e41f83496e9c58f`.
4. Resolver a `main` atual do ReqSys somente no momento em que o runner legado adquirir o job.
5. Exigir `SESSION_LAUNCH_OK` e `state_validated=true`.
6. Executar o ativador somente pelo Command Gateway com risco 2.
7. Proibir `GH_PAT_ACTIONS`, shell arbitrário, RDC, reboot e produção.
8. Usar `--non-interactive-auth` e falhar fechado se a autenticação local não autorizar o contrato.
9. Não tratar o bridge como prova terminal: o aceite final continua sendo o E2E físico da PR #17 no mesmo SHA.
10. Cancelar execução obsoleta da própria branch quando houver novo HEAD.

## Critério terminal

A ponte só é considerada funcionalmente validada quando, após sua execução, o smoke físico da PR #17 comprovar no SHA `05f9c63253f7da1eb73d88db5494a98471f0df2e`:

- `SESSION_LAUNCH_OK`;
- readback das labels;
- `WORKER_POOL_RUNTIME_SMOKE_PASSED`;
- `WORKER_POOL_SMOKE_PASSED`;
- replay idempotente;
- leitura independente.

## Fora de escopo

- deploy ou promoção;
- produção;
- reboot/shutdown;
- segredos;
- alteração do runner legado;
- merge automático sem E2E físico.
