# Proteção governada do engineering-worker-pool/main

## Objetivo

Fechar o gap de governança do repositório `ericson-j-santos/engineering-worker-pool` com custo adicional zero, aplicando branch protection real e habilitando auto-merge por rota administrativa fixa, auditável e fail-closed, com PC24x7 como primário e Noteri como fallback governado.

## Requisitos

1. Reutilizar o workflow existente `Branch Protection Audit`; não criar workflow adicional.
2. A rota primária deve executar somente por `workflow_dispatch` no modo exato `apply-engineering-worker-pool`.
3. Se o PC24x7 não adquirir o job, a rota de fallback deve executar somente por `workflow_dispatch` no modo exato `apply-engineering-worker-pool-noteri`.
4. O Authorized Actions Gateway deve aceitar somente os comandos literais `/reqsys run protect-engineering-worker-pool-main` e `/reqsys run protect-engineering-worker-pool-main-noteri`.
5. A rota primária deve usar `[self-hosted, Windows, X64, pc24x7, reqsys-dev]` e exigir `DESKTOP-PDQK954`; o fallback deve usar `[self-hosted, Windows, X64, noteri, reqsys-dev]` e exigir `Noteri`.
6. A sessão deve passar por `session_launcher.py`, exigir `SESSION_LAUNCH_OK`, `state_validated=true` e o SHA atual do ReqSys; no Noteri, a origem deve ser o checkout imutável `${{ github.workspace }}` do próprio run, sem depender de clone fixo em `C:\\dev`.
7. A mutação deve passar exclusivamente por `owner_risk3_gateway.py` com action `reqsys.engineering-worker-pool-main-protection.dev` e escopo `repo://ericson-j-santos/engineering-worker-pool/branch/main`.
8. O alvo, branch, check e comandos não podem ser recebidos por input livre.
9. O executor local da mutação deve aceitar somente os hosts exatos `DESKTOP-PDQK954` e `Noteri`; qualquer terceiro host deve falhar fechado antes de autenticação ou escrita GitHub. A autenticação GitHub deve usar somente o perfil local existente do `gh`; subprocessos removem `GH_TOKEN` e `GITHUB_TOKEN`.
10. Antes da mutação, capturar o SHA corrente de `engineering-worker-pool/main` e exigir o check `test` como `completed/success`.
11. A branch protection deve exigir Pull Request, `test` com `strict=true`, enforcement para administradores e bloquear force-push e exclusão.
12. O repositório deve terminar com `allow_auto_merge=true`.
13. O SHA da branch deve ser relido antes e depois da mutação e permanecer idêntico.
14. A proteção e o estado de auto-merge devem ser relidos por API após a mutação.
15. Se o estado já estiver correto, a execução deve ser idempotente e terminar como `ALREADY_COMPLIANT`.
16. A autorização Risk3 temporária deve ser removida em `always()`.
17. A evidência não pode conter credenciais e não pode tocar produção, deploy, banco ou conteúdo da branch.

## Critérios de aceite

- O modo de auditoria existente permanece somente leitura.
- A rota primária permanece no PC24x7 allowlisted; o fallback executa somente no Noteri allowlisted e host exato, usando checkout imutável como origem da sessão; o executor compartilhado rejeita qualquer host fora de `DESKTOP-PDQK954`/`Noteri`.
- O SHA alvo é estável antes/depois da mutação.
- O check `test` do SHA corrente está verde antes da escrita.
- A API confirma `protected=true`, Pull Request obrigatório, enforcement para admins, `test` strict, force-push bloqueado e exclusão bloqueada.
- A API do repositório confirma `allow_auto_merge=true`.
- O fluxo é idempotente e publica evidência sanitizada com leitura independente.
- Nenhum segredo, deploy ou produção é tocado.
