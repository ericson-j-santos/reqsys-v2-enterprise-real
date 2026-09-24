# Proteção governada do engineering-worker-pool/main

## Objetivo

Fechar o gap de governança do repositório `ericson-j-santos/engineering-worker-pool` com custo adicional zero, aplicando branch protection real e habilitando auto-merge por uma rota administrativa fixa, auditável e fail-closed no PC24x7.

## Requisitos

1. Reutilizar o workflow existente `Branch Protection Audit`; não criar workflow adicional.
2. A mutação deve executar somente por `workflow_dispatch` no modo exato `apply-engineering-worker-pool`.
3. O Authorized Actions Gateway deve aceitar apenas o comando literal `/reqsys run protect-engineering-worker-pool-main`.
4. O job deve executar no runner `[self-hosted, Windows, X64, pc24x7, reqsys-dev]` e exigir o host `DESKTOP-PDQK954`.
5. A sessão deve passar por `session_launcher.py`, exigir `SESSION_LAUNCH_OK`, `state_validated=true` e o SHA atual do ReqSys.
6. A mutação deve passar exclusivamente por `owner_risk3_gateway.py` com action `reqsys.engineering-worker-pool-main-protection.dev` e escopo `repo://ericson-j-santos/engineering-worker-pool/branch/main`.
7. O alvo, branch, check e comandos não podem ser recebidos por input livre.
8. A autenticação GitHub deve usar somente o perfil local existente do `gh`; subprocessos removem `GH_TOKEN` e `GITHUB_TOKEN`.
9. Antes da mutação, capturar o SHA corrente de `engineering-worker-pool/main` e exigir o check `test` como `completed/success`.
10. A branch protection deve exigir Pull Request, `test` com `strict=true`, enforcement para administradores e bloquear force-push e exclusão.
11. O repositório deve terminar com `allow_auto_merge=true`.
12. O SHA da branch deve ser relido antes e depois da mutação e permanecer idêntico.
13. A proteção e o estado de auto-merge devem ser relidos por API após a mutação.
14. Se o estado já estiver correto, a execução deve ser idempotente e terminar como `ALREADY_COMPLIANT`.
15. A autorização Risk3 temporária deve ser removida em `always()`.
16. A evidência não pode conter credenciais e não pode tocar produção, deploy, banco ou conteúdo da branch.

## Critérios de aceite

- O modo de auditoria existente permanece somente leitura.
- O novo modo executa somente no PC24x7 allowlisted.
- O SHA alvo é estável antes/depois da mutação.
- O check `test` do SHA corrente está verde antes da escrita.
- A API confirma `protected=true`, Pull Request obrigatório, enforcement para admins, `test` strict, force-push bloqueado e exclusão bloqueada.
- A API do repositório confirma `allow_auto_merge=true`.
- O fluxo é idempotente e publica evidência sanitizada com leitura independente.
- Nenhum segredo, deploy ou produção é tocado.
