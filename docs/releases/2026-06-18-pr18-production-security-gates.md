# Release notes — PR #18 — Production Security Gates

## Identificação

| Campo | Valor |
| --- | --- |
| PR | #18 |
| Título | `fix: enforce production security gates` |
| Branch de origem | `fix/prod-security-gates` |
| Branch base | `main` |
| Merge commit | `1dc4da04c993993bd258ab834214f6cc4c85d5e4` |
| Data do merge | 2026-06-18 |
| Incremento pós-merge | `docs/pr18-pos-merge-evidencias` |

## Resumo executivo

O PR #18 adicionou gates bloqueantes para impedir que a API suba em produção com configuração insegura. A decisão canônica é falhar cedo no boot quando os requisitos mínimos de segurança não forem atendidos.

## Gates aplicados

| Gate | Condição bloqueante |
| --- | --- |
| Auth demo em produção | `ALLOW_DEMO_LOGIN=true` com `APP_ENV=production`, `prod` ou `prd` |
| CORS aberto | `CORS_ORIGINS=*` em produção |
| JWT secret fraco | `JWT_SECRET` ausente, padrão ou com menos de 32 caracteres |
| JWT issuer ausente | `JWT_ISSUER` vazio em produção |
| JWT audience ausente | `JWT_AUDIENCE` vazio em produção |
| JWT expiração inválida | `JWT_EXP_MINUTES <= 0` em produção |

## Evidências técnicas

- `backend/app/core/config.py` contém `validate_production_gates()` com validação dos gates mínimos.
- `backend/app/core/security.py` emite JWT com `iat`, `exp`, `iss` e `aud` quando configurados.
- O decode do JWT valida `issuer` e `audience` quando configurados.
- `backend/app/api/auth.py` bloqueia login demo fora dos ambientes permitidos.
- `.github/workflows/ci.yml` inclui CI de backend, frontend e Playwright responsivo.
- `.github/workflows/validacao-acessos.yml` adiciona validação manual/agendada de URLs públicas.

## Testes e validações

| Categoria | Evidência |
| --- | --- |
| Backend lint/security | `ruff`, `pip-audit`, `bandit` no CI |
| Backend tests | `pytest` com cobertura mínima |
| Frontend build/audit | `npm audit` e build Vite |
| Responsividade | Playwright em mobile, tablet e desktop |
| Gates individuais | Testes dedicados para CORS, JWT e configuração de produção |

## Pós-merge obrigatório

1. Executar o workflow `Validação de Acessos Públicos — ReqSys` com `fail_on_unavailable=true`.
2. Arquivar o artefato `validacao-acessos-publicos.json`.
3. Conferir secrets reais de produção antes do próximo deploy.
4. Registrar falhas de disponibilidade como issue operacional separada.

## Rollback

Em caso de falha operacional não corrigível por configuração:

1. Reverter o merge commit `1dc4da04c993993bd258ab834214f6cc4c85d5e4`.
2. Restaurar variáveis anteriores somente em ambiente não produtivo.
3. Manter `ALLOW_DEMO_LOGIN=false`, `CORS_ORIGINS` explícito e JWT com `issuer/audience` em produção.

## Observações

A validação direta das URLs públicas deve ocorrer via GitHub Actions, pois ambientes locais ou restritos podem não resolver domínios públicos como `fly.dev` de forma confiável.
