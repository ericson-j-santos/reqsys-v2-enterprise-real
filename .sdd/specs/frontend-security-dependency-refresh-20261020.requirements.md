# Frontend Security Dependency Refresh — Requisitos

## Objetivo

Eliminar as vulnerabilidades `high` atualmente bloqueantes do `npm audit` do frontend
sem mudança funcional intencional da aplicação.

## Classificação

`gap_fix` de segurança em dependências de desenvolvimento/runtime existentes.

## Requisitos

1. Atualizar Vite dentro da linha 8.2 para uma versão corrigida dos advisories de 06/10/2026.
2. Manter a atualização em patch: `vite 8.2.4`.
3. Atualizar a cadeia necessária do Vite de forma coerente:
   `rolldown 1.2.4`, bindings `@rolldown/* 1.2.4` e
   `@oxc-project/types 0.144.0`.
4. Atualizar `follow-redirects` de 1.16.0 para 1.16.1 sem alterar a versão direta do Axios.
5. `package.json` e `package-lock.json` devem permanecer consistentes para `npm ci`.
6. Não usar `npm audit fix --force`, major upgrade ou exceção/supressão de audit.
7. Não reduzir `--audit-level=high`.
8. O build Vite deve continuar concluindo.
9. O teste de regressão deve falhar se Vite ficar abaixo de 8.2.4 ou
   `follow-redirects` abaixo de 1.16.1.
10. O teste também deve exigir Rolldown 1.2.4, `@oxc-project/types 0.144.0`
    e todos os 14 bindings Rolldown em 1.2.4.
11. Nenhum deploy, mudança de ambiente, segredo ou configuração de produção.
12. O aceite final depende do `npm audit --audit-level=high` real no CI.

## Critérios de aceite

- SDD e READY_FOR_PR verdes no SHA;
- `npm ci` verde;
- `npm audit --audit-level=high` sem findings high;
- `npm run build` verde;
- teste de regressão de versões verde;
- nenhuma alteração fora de `frontend/package*.json`, especificação e teste de prevenção.

## Correção adicional de segurança — 02/11/2026 (PR #3120)

O CI principal [#41379864410](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/41379864410) falhou em `npm audit --audit-level=high` por `GHSA-mrwp-f3q8-3g9p`: `follow-redirects 1.16.1`, afetado. A versão corrigida publicada é `1.16.2` (CVE-2026-116689).

### Requisitos
- Atualizar exclusivamente o nó `node_modules/follow-redirects` em `frontend/package-lock.json` (versão, URL e integridade SHA-512), mantendo as demais dependências inalteradas.
- `axios 1.20.0` exige `follow-redirects ^1.16.0`, portanto o patch não requer alterar dependência direta ou adotar major version.
- Atualizar `tests/test_frontend_security_dependencies.py` para exigir a nova versão e integridade, detectando regressão para a vulnerabilidade.
- Manter todos os gates de segurança; não reduzir `npm audit --audit-level=high`, não usar `--force`, não liberar merge sem CI e E2E aplicáveis.
- As demais ocorrências `moderate` são independentes e permanecem sob triagem, sem redução da segurança.

### Critérios de aceite
- `npm ci` instala a versão 1.16.2, preservando coerência do lockfile.
- `npm audit --audit-level=high` não reporta falhas `high`.
- Testes de dependência, build Vite e SDD são aprovados no HEAD final.
- Nenhum deploy, alteração de segredo ou merge automático.
