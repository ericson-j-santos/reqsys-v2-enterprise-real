# Gateway autorizado — validação pública estrita da main

## Objetivo

Permitir validar, após publicação do GitHub Pages, as URLs públicas do ReqSys no SHA corrente da main usando somente o workflow versionado de validação pública, sem URL, branch, ambiente ou política de falha arbitrários.

## Requisitos

1. O gateway deve aceitar somente o comando literal `/reqsys run validate-public-access-current-main`.
2. O comando deve permanecer restrito à issue #1705 e ao ator `ericson-j-santos`.
3. O workflow alvo deve ser fixo em `validacao-acessos.yml`.
4. A referência deve ser fixa em `main`.
5. O input `fail_on_unavailable` deve ser fixo em `true`.
6. Nenhuma URL, branch, workflow, target ou política de tolerância pode vir do comentário.
7. O workflow alvo deve continuar validando o SHA do checkout e falhar quando endpoint obrigatório estiver indisponível ou com status inesperado.
8. O comando não autoriza deploy, promoção, alteração de HML/PROD nem mutação de runtime.
9. Nenhum workflow novo deve ser criado para esta capacidade.
10. A evidência final deve vir do run alvo exato; dispatch aceito não equivale a validação concluída.

## Critérios de aceite

- teste de contrato confirma comando, workflow, ref e input exatos;
- `fail_on_unavailable=false` não é despachado pela rota governada;
- não existe input livre de URL/target;
- Pre-PR Readiness fica verde no HEAD exato e base atual;
- após merge, o run alvo `Validação de Acessos Públicos — ReqSys` deve ser terminal e verde para considerar a superfície pública validada.
