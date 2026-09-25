# Automação governada de proteção do observability-platform/main

## Objetivo

Aplicar proteção real na branch `main` de `ericson-j-santos/observability-platform` com custo adicional zero, sem interface gráfica e sem depender de segredo GitHub hospedado no Actions.

## Requisitos

1. Reutilizar o workflow existente `Branch Protection Audit`; não aumentar a quantidade líquida de workflows.
2. A mutação executa somente por `workflow_dispatch` no modo exato `apply-observability-platform`.
3. O Authorized Actions Gateway continua expondo somente o comando literal `/reqsys run protect-observability-platform-main`.
4. O job de aplicação executa no runner `[self-hosted, Windows, X64, pc24x7, reqsys-dev]` e exige host exato `DESKTOP-PDQK954`.
5. Toda execução física usa `session_launcher.py`, exige `SESSION_LAUNCH_OK`, `state_validated=true` e SHA do ReqSys igual a `github.sha`.
6. A mutação administrativa passa exclusivamente por `owner_risk3_gateway.py` com action fixa `reqsys.observability-main-protection.dev`, escopo fixo `repo://ericson-j-santos/observability-platform/branch/main` e autorização local temporária de no máximo 30 minutos.
7. O script governado não recebe token, senha, repositório, branch, check ou comando por input; todos os alvos são constantes versionadas.
8. A autenticação GitHub deve vir exclusivamente do perfil local já existente do `gh` no PC24x7; `GH_TOKEN` e `GITHUB_TOKEN` são removidos do ambiente dos subprocessos e nenhum valor de credencial pode ser lido, impresso ou persistido.
9. A execução captura o SHA corrente de `observability-platform/main`, comprova `test=completed/success` e `E2E Platform Evidence Gate / validate-evidence=completed/success`, relê o mesmo SHA imediatamente antes do PUT e exige o mesmo SHA depois da mutação.
10. A proteção exige os status checks `test` e `E2E Platform Evidence Gate / validate-evidence` com strict=true, Pull Request, enforcement para administradores e bloqueio de force-push e exclusão.
11. Se a branch já estiver corretamente protegida, a execução termina idempotentemente como `ALREADY_COMPLIANT` sem novo PUT.
12. Depois do PUT, a automação relê branch e proteção via API e falha fechado se qualquer invariante obrigatória estiver ausente.
13. A evidência registra somente estado sanitizado, target SHA, host e flags de segurança, nunca material de autenticação.
14. A autorização Risk3 temporária é removida em `always()` após a tentativa.
15. A automação não toca deploy, produção, banco, RBAC externo, STG/PROD nem conteúdo da branch alvo.

## Critérios de aceite

- O modo padrão `audit` permanece somente leitura e executável em runner hospedado.
- O modo `apply-observability-platform` executa somente no PC24x7 allowlisted.
- O SHA alvo é capturado em runtime e permanece idêntico antes/depois do PUT.
- Os checks reais `test` e `E2E Platform Evidence Gate / validate-evidence` precisam estar verdes no SHA capturado.
- A proteção final exige Pull Request + `test` + `E2E Platform Evidence Gate / validate-evidence`, aplica a administradores e bloqueia force-push/exclusão.
- O Risk3 action é exato, temporário, removido após a execução e não aceita comando ad-hoc.
- Nenhum valor de segredo aparece em log, artifact, commit ou argumento.
- O fluxo é idempotente e publica evidência independente de readback.
- A solução usa somente infraestrutura existente e custo adicional zero.
