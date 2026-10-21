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
