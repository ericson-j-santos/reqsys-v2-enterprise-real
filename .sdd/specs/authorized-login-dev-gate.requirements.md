# Gateway autorizado — validação de login DEV

## Objetivo

Permitir executar a validação de login do ReqSys DEV pelo Authorized Actions Gateway usando somente um comando exato, sem workflow arbitrário, parâmetros livres ou acesso a HML/PROD.

## Requisitos

1. O gateway deve aceitar somente o comando exato `/reqsys run login-dev-gate`.
2. O comando deve permanecer restrito à issue #1705 e ao ator `ericson-j-santos`.
3. O workflow alvo deve ser fixo em `login-multi-ambiente-gate.yml`.
4. A referência deve ser fixa em `main`.
5. O input deve ser fixo em `environment=dev`.
6. Nenhum nome de workflow, branch, ambiente ou input arbitrário pode vir do comentário.
7. O gateway deve manter permissões mínimas: `actions: write` e `contents: read`.
8. O fluxo não deve despachar `environment=hml` nem `environment=prod`.
9. A validação deve usar o contrato existente de login: configuração Azure pública, redirect do frontend e login demo conforme configuração publicada.
10. A evidência sanitizada do gateway deve manter `production_touched=false` e `secrets_read=false`.

## Critérios de aceite

- teste de contrato comprova comando, workflow, ref e input exatos;
- comandos não allowlisted continuam fail-closed;
- o target recebe exclusivamente `environment=dev`;
- HML/PROD não são despachados por esse comando;
- o workflow de login permanece responsável pela evidência funcional e falha fechado em bloqueio fora de PR;
- nenhuma nova superfície de workflow é criada.
