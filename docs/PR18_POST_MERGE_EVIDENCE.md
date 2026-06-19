# Evidência pós-merge — PR #18

## Contexto

Este documento registra a validação pós-merge do PR #18 (`fix: enforce production security gates`) no repositório `ericson-j-santos/reqsys-v2-enterprise-real`.

- PR: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/18
- Merge commit do PR #18: `1dc4da04c993993bd258ab834214f6cc4c85d5e4`
- Branch base: `main`
- Status do PR: fechado e mergeado

## Resultado da validação

| Item | Status | Evidência |
|---|---:|---|
| PR #18 mergeado | OK | PR fechado e mergeado em `main`. |
| Merge commit informado | OK | `1dc4da04c993993bd258ab834214f6cc4c85d5e4`. |
| Workflow principal de CI | Configurado | `.github/workflows/ci.yml` possui gatilho `push` para `main`, `master`, `develop` e `pull_request`. |
| Workflow run pós-merge associado ao SHA do PR #18 | Pendente | Consulta por SHA retornou lista vazia no conector disponível. |
| Cobertura mínima | Configurada | `pytest` com `--cov=app --cov-report=term-missing --cov-fail-under=60`. |
| Segurança backend | Configurada | `ruff`, `pip-audit`, `bandit`. |
| Segurança frontend | Configurada | `npm audit --audit-level=high`. |
| Build frontend | Configurado | `npm run build` com Vite. |
| Responsividade | Configurada | Playwright E2E em `frontend/tests/e2e/responsividade.spec.js`. |
| Acessos públicos | Configurado separadamente | `.github/workflows/validacao-acessos.yml` roda via `workflow_dispatch` e `schedule`, não por `push`. |

## Causa raiz provável da pendência

A evidência de execução automática por `push` em `main` para o merge commit `1dc4da04c993993bd258ab834214f6cc4c85d5e4` não foi localizada.

Hipóteses prováveis:

1. O GitHub Actions não disparou para esse merge commit específico.
2. A consulta disponível pelo conector não retornou runs de `push` associados ao SHA.
3. O run pode ter sido criado em outro contexto, sem associação direta ao SHA consultado.
4. A validação de acessos públicos não faz parte do fluxo de `push`, pois está em workflow separado.

## Impacto

- O PR #18 permanece mergeado.
- A implementação dos gates de segurança permanece presente no histórico.
- O ciclo ainda não possui evidência pós-merge material suficiente para declarar encerramento em padrão ouro.
- A ausência de run localizado não implica falha funcional por si só, mas impede comprovação final auditável.

## Rollback

Rollback deve ser aplicado apenas se houver falha funcional, regressão de segurança ou indisponibilidade real.

```bash
git checkout main
git pull origin main
git revert -m 1 1dc4da04c993993bd258ab834214f6cc4c85d5e4
git push origin main
```

## Ações corretivas recomendadas

1. Materializar um novo `push` em `main` com esta evidência versionada.
2. Validar se o workflow `CI — ReqSys v2 Enterprise` executou para o novo commit.
3. Executar manualmente `Validação de Acessos Públicos — ReqSys` com `fail_on_unavailable=true`.
4. Registrar no PR #18 ou em release:
   - URL do run de CI pós-merge;
   - resultado dos jobs;
   - cobertura final;
   - resultado de `pip-audit`, `bandit`, `npm audit` e Playwright;
   - artefato `validacao-acessos-publicos.json`;
   - decisão final de promoção/produção.

## Decisão atual

Status: **parcialmente validado pós-merge**.

Critérios atendidos:

- PR #18 mergeado.
- Merge commit confirmado.
- Workflows e gates configurados no repositório.
- Evidência documentada no PR e neste arquivo.

Critérios pendentes:

- Run pós-merge material associado ao commit de validação em `main`.
- Execução manual/agendada da validação de acessos públicos.
- Registro final de evidências de cobertura, segurança, build, responsividade e acessos públicos.
