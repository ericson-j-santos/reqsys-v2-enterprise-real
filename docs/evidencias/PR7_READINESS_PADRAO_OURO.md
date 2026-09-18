# PR #7 — Evidências de Readiness Padrão Ouro

Data de consolidação: 2026-06-19
Repositório: `ericson-j-santos/reqsys-v2-enterprise-real`
Branch: `codex/validate-code-and-create-tests`
Base: `main`

## Objetivo

Consolidar o PR #7 para merge seguro, cobrindo timestamps UTC-aware, runbook de publicação, scripts de publicação/teste/qualidade, build frontend offline sem dependências externas e testes aplicáveis.

## Estado técnico validado por inspeção

| Área | Evidência | Status |
|---|---|---|
| Backend UTC-aware | `backend/app/api/dashboard.py` importa `UTC` e usa `datetime.now(UTC).isoformat()` | OK |
| Sistema UTC-aware | `backend/app/api/sistema.py` importa `UTC` e usa `datetime.now(UTC).isoformat()` | OK |
| Testes de timestamp | `backend/tests/test_dashboard.py` valida `tzinfo` e offset UTC zero | OK |
| Runbook publicação | `docs/RUNBOOK_PUBLICACAO_1PAGINA.md` cobre DEV, HML, PROD, qualidade e reversão | OK |
| Script publicação | `scripts/publicar_ambiente.sh` cobre `dev`, `hml` e `prod` | OK |
| Script smoke URLs | `scripts/testar_urls_ambiente.sh` cobre frontend, health e readiness por ambiente | OK |
| Script qualidade | `scripts/validar_qualidade.sh` executa testes backend, builds frontend e E2E | OK |
| Frontend offline | `frontend-angular/src/index.html` não carrega Google Fonts ou Material Icons externos | OK |

## Validação recomendada

- Backend: executar `PYTHONPATH=. pytest -q` dentro de `backend`.
- Angular: executar `npm ci`, `npm run build` e testes Jest aplicáveis dentro de `frontend-angular`.
- Vuetify: executar `npm ci` e `npm run build` dentro de `frontend-vuetify`, quando aplicável.
- Gate consolidado: executar `bash scripts/validar_qualidade.sh`.
- Smoke: executar `bash scripts/testar_urls_ambiente.sh dev`, `hml` e `prod` conforme ambiente disponível.

## Changelog

### Adicionado

- `scripts/testar_urls_ambiente.sh` para validação objetiva das URLs de frontend, API health e API readiness em `dev`, `hml` e `prod`.
- Dossiê de evidências para rastreabilidade do PR #7.

### Alterado

- `frontend-angular/src/index.html` deixou de carregar fontes e ícones por links externos, reduzindo fragilidade em CI/offline e ambientes corporativos restritos.

### Confirmado

- Timestamps UTC-aware no backend.
- Testes de regressão para timestamp UTC-aware.
- Runbook de publicação em uma página.
- Script de publicação por ambiente.
- Script de qualidade consolidado.

## Rollback

Rollback preferencial: reverter o merge commit do PR #7.

Rollback operacional: retornar para a tag ou commit estável anterior e republicar a stack com os mesmos manifests de produção.

Critérios para rollback:

- falha de health/readiness após publicação;
- regressão de autenticação ou CORS em ambiente controlado;
- regressão no build frontend;
- timestamp sem timezone ou offset diferente de UTC;
- falha de smoke test das URLs críticas.

## Decisão de merge

O PR #7 fica apto para merge quando o GitHub Actions concluir com sucesso após os commits desta consolidação e o estado do PR retornar como mergeable.
