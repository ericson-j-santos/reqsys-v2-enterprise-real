# Automação governada de proteção do observability-platform/main

## Objetivo

Aplicar proteção real na branch `main` de `ericson-j-santos/observability-platform` sem custo adicional e sem depender de interface gráfica.

## Requisitos

1. Reutilizar o workflow existente `Branch Protection Audit`; não aumentar a quantidade líquida de workflows.
2. A mutação deve executar somente por `workflow_dispatch` no modo exato `apply-observability-platform`.
3. O Authorized Actions Gateway deve expor apenas o comando literal `/reqsys run protect-observability-platform-main`.
4. O repositório alvo e a branch devem ser fixos: `ericson-j-santos/observability-platform` e `main`.
5. A execução deve falhar fechado se a `main` alvo divergir do SHA esperado.
6. A execução deve comprovar que o check real `test` está verde no SHA alvo antes da mutação.
7. A proteção deve exigir status check `test` atualizado, exigir Pull Request, aplicar também a administradores e bloquear force-push e exclusão da `main`.
8. A credencial administrativa deve permanecer em `secrets.GITHUB_PAT`, usada apenas em memória; nenhum valor de segredo pode ir para log, artifact ou commit.
9. Depois do PUT, a automação deve reler a proteção via API e falhar se qualquer invariante obrigatória não estiver ativa.
10. A evidência deve registrar repositório, branch, SHA esperado, check obrigatório e flags de segurança, sem material secreto.
11. A automação não deve tocar deploy, produção, banco, RBAC externo ou ambientes STG/PROD.
