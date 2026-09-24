# Automação governada de proteção do e2e-platform/main

## Objetivo

Aplicar proteção real na branch `main` de `ericson-j-santos/e2e-platform` com custo adicional zero, sem interface gráfica e sem segredo GitHub hospedado no Actions.

## Requisitos

1. Reutilizar o workflow existente `Branch Protection Audit`; não criar workflow adicional.
2. A mutação executa somente por `workflow_dispatch` no modo exato `apply-e2e-platform`.
3. O Authorized Actions Gateway expõe somente o comando literal `/reqsys run protect-e2e-platform-main`.
4. O job executa no runner `[self-hosted, Windows, X64, pc24x7, reqsys-dev]` e exige host exato `DESKTOP-PDQK954`.
5. Toda execução física usa `session_launcher.py`, exige `SESSION_LAUNCH_OK`, `state_validated=true` e SHA do ReqSys igual a `github.sha`.
6. A mutação administrativa passa exclusivamente por `owner_risk3_gateway.py` com action fixa `reqsys.e2e-platform-main-protection.dev`, escopo fixo `repo://ericson-j-santos/e2e-platform/branch/main` e autorização local temporária de no máximo 30 minutos.
7. Repositório, branch, check e comando são constantes versionadas; não são aceitos como input.
8. A autenticação GitHub vem apenas do perfil local existente do `gh` no PC24x7; `GH_TOKEN` e `GITHUB_TOKEN` são removidos dos subprocessos.
9. A execução captura o SHA corrente de `e2e-platform/main`, exige `contract-self-test=completed/success` e relê o mesmo SHA imediatamente antes e depois da mutação.
10. A proteção exige `contract-self-test` com strict=true, Pull Request, enforcement para administradores e bloqueio de force-push e exclusão.
11. Se a branch já estiver conforme, a execução termina idempotentemente como `ALREADY_COMPLIANT`.
12. Após o PUT, a automação relê branch e proteção e falha fechado diante de qualquer divergência.
13. A evidência é sanitizada e não contém material de autenticação.
14. A autorização Risk3 temporária é removida em `always()`.
15. A automação não toca deploy, produção, banco, STG/PROD nem conteúdo da branch alvo.

## Critérios de aceite

- O modo `audit` permanece somente leitura.
- O modo `apply-e2e-platform` executa somente no PC24x7 allowlisted.
- O SHA alvo permanece idêntico antes/depois.
- `contract-self-test` precisa estar verde no SHA capturado.
- A proteção final exige Pull Request + `contract-self-test`, enforce admins e bloqueia force-push/exclusão.
- O Risk3 action é exato, temporário e removido após a execução.
- Nenhum segredo aparece em log, artifact, commit ou argumento.
- O fluxo é idempotente e publica evidência de readback independente.
- A solução usa somente infraestrutura existente e custo adicional zero.
