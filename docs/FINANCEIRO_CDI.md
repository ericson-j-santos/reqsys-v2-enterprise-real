# Financeiro · Provedor interno de CDI

Documentação viva da feature de taxa CDI (ADR-012: estado atual vs. estado alvo vs. gaps pendentes,
sempre diferenciados explicitamente abaixo).

## O que é

Provedor interno e gratuito da taxa CDI diária, com o Banco Central do Brasil (série SGS 12) como
fonte primária pública e um cache local governado (`cdi_rates`) que permite responder mesmo quando o
BCB está indisponível (fallback com `stale=true`).

## Estado atual (implementado e validado)

### Backend

| Componente | Arquivo |
|---|---|
| Modelo/cache SQLite | `backend/app/models/cdi_rate.py` |
| Provider (fetch BCB + upsert + fallback) | `backend/app/services/cdi_provider.py` |
| Retry + circuit breaker genéricos | `backend/app/core/resilience.py` |
| API | `backend/app/api/financeiro.py` |
| Testes | `backend/tests/test_cdi_provider.py`, `backend/tests/test_financeiro_api.py`, `backend/tests/test_resilience.py` |

Endpoints:

- `GET /v1/financeiro/cdi/latest` — retorna o último valor em cache (`404` se o cache ainda estiver vazio).
- `POST /v1/financeiro/cdi/refresh` — protegido por `require_admin`; consulta o BCB, atualiza o cache e
  registra evento de auditoria (`CDI_REFRESH_SUCESSO` / `CDI_REFRESH_FALHA`, com `correlation_id` e
  usuário responsável). Se o BCB falhar e existir cache, responde `200` com o último valor conhecido
  marcado `stale=true` e `meta.warning`; sem cache, responde `502`.

Resiliência (ADR-010 — timeout + retry com backoff + circuit breaker + idempotência em escrita):

- Timeout de 10s na chamada HTTP ao BCB.
- Retry exponencial (3 tentativas, 0.5s/1s) apenas para falhas transitórias de rede/JSON — erro de
  payload malformado não é retried (não é transitório).
- Circuit breaker (abre após 3 falhas consecutivas, cooldown de 60s) para não martelar o BCB quando
  ele está fora do ar.
- Escrita idempotente: `upsert` por `(reference_date, source)` via `UniqueConstraint`.

Governança: a fonte está registrada e auditada em `config/external-sources-registry.json`
(`id: "bcb-sgs-cdi"`, `mock_as_real: false`, `autorizado: true`).

### Frontend (Vue 3 / Vuetify — `frontend/`)

| Componente | Arquivo |
|---|---|
| Service (axios) | `frontend/src/services/financeiro.js` |
| View | `frontend/src/views/FinanceiroView.vue` |
| Teste do service | `frontend/src/services/__tests__/financeiro.test.js` |

- Rota `/financeiro` registrada em `frontend/src/router/index.js` (`meta.recurso: 'dashboard:read'`,
  mesmo padrão de acesso da tela de Estatísticas).
- Item de menu em `frontend/src/constants/navCatalog.js`, tema "Operação".
- Página segue o padrão ADR-009 já usado em `EstatisticasView.vue`: cards com `OperationalMetricCard`
  (taxa % , taxa decimal, referência, status do cache) e um bloco de drill-down com fonte, URL da
  fonte, confiabilidade, data de coleta e fórmula.
- Botão "Atualizar do Banco Central" visível apenas quando `auth.usuario?.papel === 'admin'`, alinhado
  com o `require_admin` do backend.
- Modo offline (API indisponível) e "cache vazio" (`404`, ainda não populado) são tratados como estados
  distintos, sem inventar dado.

### Reprodução automatizada

`scripts/scaffold_cdi_feature.py` — gerador autocontido (stdlib apenas, sem dependências externas) que
escreve em disco todos os arquivos novos da feature (backend + testes + frontend) e aplica patches
idempotentes nos arquivos existentes que precisam registrar a feature (roteamento do backend, registro
de modelos, roteamento/menu do frontend, registry de fontes externas). Seguro para reexecutar: arquivos
já idênticos são pulados, arquivos existentes com conteúdo diferente só são sobrescritos com `--force`.

```bash
python scripts/scaffold_cdi_feature.py --dry-run   # mostra o que seria feito
python scripts/scaffold_cdi_feature.py             # escreve de fato
```

## Estado alvo

- Retry + circuit breaker (`app/core/resilience.py`) adotado por **todos** os adapters externos do
  projeto, não só o CDI — hoje é o único consumidor do helper compartilhado.
- Histórico de séries CDI (não só o último valor) exposto via endpoint próprio, para cálculo de
  rentabilidade acumulada em período.
- Testes E2E (Playwright) da tela `/financeiro`, no mesmo padrão de `frontend/tests/e2e/estatisticas.spec.js`.

## Gaps pendentes

- Nenhum gap crítico bloqueando o uso atual da feature.
- `app/core/resilience.py` ainda não foi aplicado aos demais adapters externos do projeto (GitHub,
  Power Automate, etc.) — ADR-010 continua parcialmente atendido no restante do código.
- Sem endpoint de histórico/série temporal de CDI (só o último valor em cache é exposto hoje).
- Sem teste E2E de frontend para `/financeiro` (cobertura atual é unitária, no service).

## Como validar

```bash
# Backend
cd backend
.venv/Scripts/python.exe -m pytest tests/test_cdi_provider.py tests/test_financeiro_api.py tests/test_resilience.py -q
.venv/Scripts/python.exe -m ruff check app/models/cdi_rate.py app/services/cdi_provider.py app/core/resilience.py app/api/financeiro.py tests/test_cdi_provider.py tests/test_financeiro_api.py tests/test_resilience.py

# Frontend
cd frontend
npx vitest run src/services/__tests__/financeiro.test.js
```
