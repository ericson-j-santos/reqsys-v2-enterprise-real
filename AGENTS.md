# AGENTS.md

Guia operacional canônico para agentes, automações e assistentes que atuam neste repositório. Mantenha este arquivo objetivo, rastreável e alinhado ao estado real do código.

## Princípios de trabalho

- Priorizar mudanças pequenas, revisáveis e com escopo explícito.
- Não executar ações destrutivas sem evidência, justificativa e possibilidade de rollback.
- Não commitar segredos, `.env`, bancos locais, artefatos de build, logs sensíveis ou arquivos temporários.
- Preferir documentação em português do Brasil quando o conteúdo for operacional ou de produto.
- Validar comandos antes de documentá-los. Quando houver dúvida, registrar como pendência em vez de assumir.

## Estrutura principal

| Caminho | Responsabilidade |
| --- | --- |
| `backend/` | API principal FastAPI, domínio, serviços, integrações e testes Python. |
| `frontend/` | Frontend principal Vue/Vite/Vuetify. |
| `backend-dotnet/` | Serviço .NET complementar, quando aplicável. |
| `frontend-angular/` | Frente Angular complementar ou experimental. |
| `frontend-vuetify/` | Variante Vuetify usada em validações específicas. |
| `e2e/` e `frontend/tests/e2e/` | Testes Playwright e validações responsivas. |
| `.github/workflows/` | CI, quality gates e validações agendadas/manuais. |
| `docs/` | Decisões, runbooks, evidências e documentação operacional. |
| `scripts/` | Automação local, publicação, validação e tarefas auxiliares. Subdiretório `scripts/governance/` para gates de governança enterprise. Equivalentes Windows PowerShell em `scripts/*.ps1`. |
| `artifacts/` | Saída de artifacts CI/evidência (JSON, dashboards, snapshots). |
| `audit/` | Relatórios de auditoria e evidence consolidada. |
| `infra/` | Configuração de infraestrutura: nginx, codex-local (Ollama/Qdrant), ambientes Fly.io. Manifesto canônico de ambientes em `infra/fly-environments.json`. Subdiretórios por ambiente (`dev/`, `hml/`, `prod/`) e reverse-proxy. |
| `contracts/openapi/` | Contratos OpenAPI (lintado por workflows Spectral/Newman). |
| `schemas/` | Schemas JSON de governança e product-intelligence. |
| `tools/` | Ferramentas standalone: codex-local-online, product_intelligence, schema_governance. |
| `tests/` | Testes de integração/governança para scripts e workflows (não confundir com `backend/tests/`). |
| `docs-site/` | Site MkDocs publicado em GitHub Pages. |
| `config/` | Arquivos de configuração auxiliares. |

## Comandos essenciais

### Backend FastAPI

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v --tb=short
python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-fail-under=60
```

Em Windows PowerShell, ative o ambiente virtual com:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
```

### Qualidade e segurança backend

```bash
cd backend
ruff check app/ --select E,F,W,I --ignore E501
pip-audit -r requirements.txt
bandit -r app/ -ll -x app/tests
```

### Frontend principal

```bash
cd frontend
npm ci
npm audit --audit-level=high
npm run build
npx playwright install --with-deps chromium
npx playwright test tests/e2e/responsividade.spec.js
```

Testes unitários (Vitest):

```bash
cd frontend
npm run test:unit          # vitest run
npm run test:coverage      # vitest run --coverage
```

E2E estável:

```bash
cd frontend
npm run test:e2e:stable    # node scripts/run-e2e-safe.js --reporter=line
```

### Docker e publicação local

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Quando existir script dedicado, preferir o wrapper versionado:

```bash
bash scripts/publicar_ambiente.sh dev
bash scripts/publicar_ambiente.sh hml
bash scripts/publicar_ambiente.sh prod
```

### Dev local sem Docker

```bash
bash scripts/dev-local.sh
# Variáveis opcionais: BACKEND_PORT, FRONTEND_PORT, DEV_DB_PATH, REQSYS_SKIP_BACKEND_INSTALL
```

Stack completa com nginx:

```bash
bash scripts/executar-local.sh
# Variáveis opcionais: GATEWAY_PORT, BACKEND_PORT, FRONTEND_PORT, KB_PORT, KB_DIR
```

### Segurança — testes de gate

```bash
bash scripts/run_security_gate_tests.sh
# Executa: test_security_production_gates_individual.py, test_security_cors_individual.py, test_security_auth_jwt_individual.py
```

### Validação de qualidade

```bash
bash scripts/validar_qualidade.sh
# Executa: pytest backend, build frontend-vuetify + frontend-angular, E2E/acessibilidade
```

### Health check de URLs por ambiente

```bash
bash scripts/testar_urls_ambiente.sh dev
bash scripts/testar_urls_ambiente.sh hml
bash scripts/testar_urls_ambiente.sh prod
```

### Cofre operacional (vault)

```bash
python scripts/vault_setup.py init              # cria master key
python scripts/vault_setup.py set KEY VALUE     # grava segredo
python scripts/vault_setup.py get KEY           # lê segredo
python scripts/vault_setup.py status            # estado do vault
python scripts/vault_setup.py import-env        # importa .env para o vault
python scripts/vault_setup.py gen-token         # gera VAULT_API_TOKEN
```

### OpenAPI / contratos

```bash
python scripts/validate_openapi_contract.py --contract docs-site/assets/openapi/reqsys-runtime-openapi-*.json
python scripts/openapi_semantic_diff.py          # diff OpenAPI vs rotas FastAPI (report-only)
python scripts/generate_postman_from_openapi.py # gera coleção Postman v2.1
```

### Validação de acessos públicos

```bash
npm run validate:access                         # validar-acessos-publicos.mjs
npm run validate:pipeline                       # validar-pipeline-governanca.mjs
npm run validate:dashboard-regression           # validate-dashboard-regression.mjs
```

### Auditoria de produção

```bash
python scripts/prod_readiness_audit.py
# Verifica endpoints Fly.io, segredos obrigatórios, gates. Output: artifacts/prod-readiness-audit.json
```

### Guardrails enterprise CI

```bash
python scripts/ci_enterprise_guardrails.py
# Validações determinísticas rápidas (configs inseguras, não-determinismo)
```

### Gates de merge e PR

```bash
python scripts/merge_readiness_gate.py                 # branch atrasada, conflito, PR grande, excesso de workflows, domínios misturados
python scripts/conflict_prediction_gate.py             # risco de conflito por paths alterados (determinístico, sem IA)
python scripts/runtime_merge_queue_gate.py --lane runtime-governance --ci green --runtime-smoke green --incidents none-critical --contracts green --json
python scripts/pr_quality_review.py                    # revisão automatizada de PR: risco, escopo, arquivos sensíveis
```

### Validação de ambientes Fly.io

```bash
python scripts/validate_fly_runtime_config.py          # valida config versionada do Fly (read-only, sem deploy)
python scripts/validate_fly_enterprise_sync.py         # valida matriz canônica de ambientes Fly.io
python scripts/validate_dev_environment_readiness.py  # valida ambiente dev (evidence artifact, não exige endpoints verdes)
python scripts/validate_environment_promotion_readiness.py  # valida contrato de promoção DEV→STG→PROD
python scripts/environment_drift_analyzer.py           # drift cross-ambiente (report-only)
python scripts/executive_readiness_gate.py             # decisão única de promoção de ambiente (report-only)
```

### Validação de autenticação

```bash
python scripts/validar_login_azure_operacional.py --api-url https://reqsys-api-dev.fly.dev
python scripts/validar_login_multi_ambiente.py         # valida login Azure AD + demo em todos ambientes Fly
python scripts/validar_frontend_auth_redirect.py --dist-dir frontend/dist  # valida redirect URI no bundle
python scripts/configurar_fly_auth_azure.py            # configura secrets Azure AD no Fly.io (nunca imprime valores)
```

### Validação de segurança e runtime

```bash
python scripts/validate_security_baseline.py           # secret scanning, CORS, TLS, PII em logs (read-only, CI)
python scripts/check_encoding.py                       # detecta mojibake em Python source files
python scripts/validate_public_runtime.py              # smoke público e readiness (read-only)
python scripts/runtime_production_smoke_governed.py    # smoke governado de endpoints públicos essenciais
python scripts/runtime_public_validator.py             # validador público do runtime
```

### Padrão Ouro e maturidade

```bash
python scripts/trilhas_padrao_ouro.py                  # consolidador Trilhas A–E do Padrão Ouro
python scripts/padrao_ouro_scorecard.py                # scorecard executivo de maturidade
python scripts/delivery_maturity_snapshot.py           # snapshot de maturidade de entrega
python scripts/operational_cycle_complete_gate.py      # gate determinístico para ciclo Trilha D
```

### Pós-merge e operacional

```bash
python scripts/post_merge_main_runtime_validator.py    # valida evidência runtime pós-merge (offline, lê artifacts locais)
python scripts/actions_auto_operator.py                # rerun automático de workflows allowlisted com falha transitória
python scripts/workflow_command_center.py              # monitora e dispatcha workflows governados
python scripts/coordenador_status_consolidator.py      # consolida status do coordenador em artifact
```

### Seleção de testes e scaffolding

```bash
python scripts/select_backend_tests.py                 # seleciona testes backend afetados pelo diff (fallback para suite completa)
python scripts/scaffold_cdi_feature.py [--dry-run] [--force]  # scaffold autocontido da feature Financeiro/CDI
python scripts/replicate_requisitos_anonimizado.py --dry-run  # replica requisitos com anonimização LGPD (dry-run por padrão)
```

## CI obrigatório

Antes de merge em `main`, validar o workflow `CI — ReqSys v2 Enterprise` com os jobs:

| Job | Gate esperado |
| --- | --- |
| `CI Router (paths + Pareto)` | detecta escopo e ativa suites relevantes |
| `Backend Lint & Security (ruff + pip-audit + bandit)` | `success` |
| `Backend Tests + Coverage (pytest)` | `success` com cobertura mínima configurada |
| `Frontend Build + Security Audit (Vite + npm audit)` | `success` |
| `Frontend Responsive E2E (Playwright)` | `success` |
| `Pipeline Governança + Evidence Snapshot` | `success` |

Não considerar um PR pronto para merge quando o E2E responsivo estiver ausente, em execução ou falho, salvo decisão técnica formal e documentada.

### Workflows CI complementares

| Workflow | Trigger | Propósito |
| --- | --- | --- |
| `CI Enterprise Fast` | PR/push | Guardrails determinísticos (`ci_enterprise_guardrails.py`) |
| `Fast CI - Operational Guardrails` | PR (paths: workflows/scripts/tests/runbooks) | Sintaxe Python + testes operacionais rápidos |
| `CI E2E Governado` | PR com label `e2e`/`full-ci`, push main | E2E com routing por paths alterados |
| `CI Security Deep Scan` | Push main, PR com label `security`/`full-ci` | Scan profundo backend + frontend |
| `Main Smoke CI` | Push main, `workflow_dispatch` | Pós-merge: validação sintaxe + guardrails |
| `OpenAPI Spectral Lint` | PR (paths: openapi/contracts) | Lint de contrato OpenAPI (report-only) |
| `OpenAPI Routes Drift` | PR (paths: backend/api) | Detecta drift OpenAPI vs rotas FastAPI |
| `Docs MkDocs` | PR/push (paths: mkdocs.yml, docs-site/) | Build e deploy da documentação |
| `Agent Increment Gate` | `workflow_dispatch` | Gate de incremento para nova frente/gap_fix/hotfix |
| `Coordenador Status Consolidator` | Agendado, `workflow_dispatch` | Consolida status operacional do coordenador |
| `Governed Merge Queue` | PR, agendado | Merge queue governada com smoke + CI + contratos |
| `PR Evidence Gate` | PR | Evidência obrigatória antes de merge |
| `PR Conflict Guard` | PR | Predição de conflito e proteção de paths sensíveis |
| `PR Quality Review` | PR | Revisão determinística de risco/escopo do PR |
| `PR CI Watch` | PR | Monitoramento de CI em PRs abertos |
| `Main Post-Merge Validation` | Push main | Validação runtime + evidência pós-merge |
| `Fly Enterprise Sync` | Agendado, `workflow_dispatch` | Sincronização e validação de ambientes Fly.io |
| `Fly Governed Command Center` | `workflow_dispatch` | Comando governado de operações Fly.io |
| `Fly Runtime P0` | Push main | Validação P0 de runtime Fly.io pós-deploy |
| `Runtime Validation Consolidator` | Agendado, `workflow_dispatch` | Consolidação de validações runtime |
| `Runtime Health Center/Validator` | Agendado | Health check e validação de runtime |
| `Operational Governance Gate` | `workflow_dispatch` | Gate de governança operacional |
| `Security Baseline Gate` | PR | Validação de baseline de segurança |
| `Merge Readiness` | PR | Condições de merge readiness (branch, conflito, tamanho) |
| `Governed Promotion Pipeline` | `workflow_dispatch` | Pipeline de promoção dev→hml→prod governada |
| `Trilhas Padrão Ouro` | Agendado, `workflow_dispatch` | Consolidação das Trilhas A–E |
| `Governança Padrão Ouro` | Agendado | Scorecard de maturidade Padrão Ouro |
| `Workflow Command Center` | `workflow_dispatch` | Monitora e dispatcha workflows governados |
| `Operational Intelligence Hub` | Agendado | Hub de inteligência operacional |
| `Failure Pattern Engine` | Agendado, `workflow_dispatch` | Detecção de padrões de falha em CI |

## Gates de produção

Produção deve ser bloqueada se qualquer condição abaixo ocorrer:

- `APP_ENV` produtivo com `ALLOW_DEMO_LOGIN=true`.
- `CORS_ORIGINS=*`.
- `JWT_SECRET` fraco, ausente ou padrão.
- `JWT_ISSUER` ausente.
- `JWT_AUDIENCE` ausente.
- `JWT_EXP_MINUTES <= 0`.
- Logs contendo token, senha, CPF, PII, connection string ou segredo.
- Auditoria sem `correlation_id`.
- Endpoint administrativo de conector exposto sem autorização adequada.

## Deploy de hotfix e ambientes

- Quando houver mudanças locais fora do escopo do hotfix, publicar a partir de uma árvore limpa contendo somente os arquivos do ajuste aprovado.
- Para mudanças de frontend/autenticação, validar localmente com `npm run build` e teste unitário ou regressivo focado antes de publicar.
- Promover ambientes em ordem: `dev` primeiro, depois `staging`, depois `prod`.
- Após cada publicação, validar o endpoint afetado no ambiente publicado antes de seguir para o próximo.
- Não publicar produção quando o deploy puder carregar alterações locais não revisadas ou não relacionadas.

## Padrão de PR

Cada PR deve conter:

- Resumo objetivo.
- Escopo e fora de escopo.
- Evidências de teste.
- Riscos e rollback quando aplicável.
- Referência a issue, decisão técnica ou release note quando existir.

Critérios mínimos para merge:

- PR não está em draft.
- Branch está mergeável.
- CI completo e verde.
- Comentários críticos resolvidos.
- Sem mudanças fora do escopo declarado.

## Padrão de commits

Usar commits claros e preferencialmente convencionais:

```text
feat: adicionar recurso
fix: corrigir comportamento
test: adicionar cobertura
docs: atualizar documentação
ci: ajustar pipeline
chore: manutenção sem impacto funcional
```

## Segurança e segredos

- Nunca registrar valores reais de segredo em documentação, teste ou log.
- Usar placeholders seguros como `placeholder`, `example.com`, `reqsys-ci` ou equivalentes.
- Não commitar `.env`, bancos SQLite locais, dumps, prints com PII ou artefatos de execução.
- Antes de publicar código que toque autenticação, CORS, JWT, conectores ou permissões, validar gates individuais e testes regressivos.

## Correlation ID e auditoria

Toda operação relevante deve preservar rastreabilidade:

- Aceitar `X-Correlation-ID` ou `X-Request-ID` quando aplicável.
- Propagar o identificador para serviços internos, logs, envelopes e auditoria.
- Gerar identificador quando o cliente não enviar.
- Não mascarar o `correlation_id`, mas mascarar PII e segredos.

## Documentação esperada

Para mudanças relevantes, atualizar pelo menos um dos itens abaixo:

- `README.md`, quando afetar uso geral.
- `docs/`, quando afetar arquitetura, segurança, operação ou runbook.
- Release note em `docs/releases/`, quando houver entrega significativa.
- Matriz de testes, quando novos gates ou cenários críticos forem adicionados.

## Orientações para agentes

- **Antes de abrir branch/PR novo**, executar o gate de incremento objetivo:
  ```bash
  python scripts/agent_increment_gate.py --increment-type new_front --intent "descricao curta"
  ```
  Com artifact local: `--status-json artifacts/coordenador-status/coordenador-status.json`.
  Tipos permitidos conforme `increment_gate.allowed_increment_types` em `coordenador-status.json`.
- Para corrigir gap: `--increment-type gap_fix --reference OPS-GAP-*`.
- Para fechar duplicado: `--increment-type close_duplicate --reference <numero_pr>`.
- Para hotfix escopo fechado: `--increment-type hotfix --reference OPS-GAP-*`.
- Para concluir incremento ativo (CI/merge): `--increment-type consolidate`.
- Workflow manual: **Agent Increment Gate** (`workflow_dispatch`).
- Não criar múltiplos PRs concorrentes para o mesmo arquivo sem necessidade.
- Quando houver PRs duplicados, consolidar o conteúdo canônico em um único PR e fechar os demais com justificativa.
- Preferir alteração mínima em arquivos existentes.
- Não fazer merge em lote de PRs antigos sem revalidar contra a `main` atual.
- Não depender de revisão automática como única evidência. CI e inspeção técnica continuam obrigatórios.

## Decisão canônica atual

O ciclo de PRs deve seguir este fluxo:

```text
triagem → ajuste mínimo → CI completo → evidência → merge controlado → validação pós-merge → fechamento de duplicados
```

Este arquivo é a referência operacional para próximos agentes que atuarem no repositório.

## Ambientes Fly.io e acesso público

Ambientes públicos definidos em `infra/public-access-urls.json` e validados por `npm run validate:access`:

| Ambiente | Frontend Fly | API Health Fly |
| --- | --- | --- |
| dev | `https://reqsys-app-dev.fly.dev/` | `https://reqsys-api-dev.fly.dev/health` |
| hml (staging) | `https://reqsys-app-stg.fly.dev/` | `https://reqsys-api-stg.fly.dev/health` |
| prod | `https://reqsys-app.fly.dev/` | `https://reqsys-api.fly.dev/health` |

Boot resiliente Fly.io: `scripts/fly_boot.sh` — garante volume gravável antes de uvicorn; fallback para `/tmp` via `REQSYS_BOOT_FALLBACK=true`.

Endpoints de runtime health disponíveis: `/health`, `/api/runtime/health`, `/api/runtime/readiness`, `/api/runtime/liveness`. Em prod, também `/api/runtime/metrics`.

Manifesto canônico de ambientes: `infra/fly-environments.json` — define promoção `dev → hml → prod`, smoke endpoints por ambiente, secrets obrigatórios e apps Fly.io. Validado por `scripts/validate_fly_enterprise_sync.py`.

## Codex Local / Ollama

Stack local de IA com Ollama + Qdrant (RAG opcional):

```bash
bash scripts/iniciar_codex_local.sh              # sobe Ollama (Docker ou nativo) + backend + frontend
bash scripts/configurar_ollama_gateway_sync.sh   # configura sync com repo externo (requer OLLAMA_GATEWAY_SYNC_TOKEN)
bash scripts/sincronizar_ollama_gateway_repo.sh  # sincroniza bootstrap com reqsys-ollama-local-gateway
```

Docker Compose dedicado: `infra/codex-local/docker-compose.ollama.yml` (Ollama na `:11434`, Qdrant no perfil `rag` na `:6333`).

## Documentação MkDocs

Site publicado em GitHub Pages via workflow `Docs MkDocs`. Para build local:

```bash
pip install -r requirements-docs.txt
mkdocs build
```

Config: `mkdocs.yml`, fonte: `docs-site/`.

## Testes de scripts (root `tests/`)

Os testes em `tests/` (raiz do repo) validam scripts e workflows de governança, não o backend:

```bash
python -m pytest tests/ -q   # testes de scripts/governança (não confundir com backend/tests/)
```

## Cursor Cloud specific instructions

Ambiente já inicializado pelo update script (venv do backend + `npm ci` no frontend). Dependencias de sistema (`unixodbc`/`unixodbc-dev` para `pyodbc` e `python3.12-venv`) ja estao no snapshot da VM; nao precisam ser reinstaladas.

### Coordenador Principal (operacao hibrida)

Automacao real fica em GitHub Actions + scripts + agentes por PR; chats fixos sao contexto, nao runtime autonomo. Menu fechado: `docs/runbooks/coordenador-principal-menu-operacional.md`. Leitura preferencial: artifact `coordenador-status-evidence` via workflow **Coordenador Status Consolidator**.

**Hub documentacao Padrão Ouro Tier 1:** `docs/padrao-ouro/README.md` - Living Architecture Index, ADR Index, Runtime Evidence Graph, Contract Catalog e Engineering Playbooks. Indice machine-readable para agentes: `docs/padrao-ouro/living-architecture-index.json`.

**Gate obrigatorio para nova frente:** `python scripts/agent_increment_gate.py --increment-type new_front --intent "<objetivo>"`. Exit code `0` = permitido; `1` = bloqueado (seguir `recommended_actions`). Campo `increment_gate.new_front_allowed` em `coordenador-status.json`.

### Servicos canonicos (modo dev, sem Docker)

A forma mais leve de rodar o produto e backend uvicorn + frontend Vite (o Vite faz proxy de `/api` para o backend, conforme `frontend/vite.config.js`). Nginx/KB/Docker nao sao necessarios para o fluxo principal.

- Backend (`:8000`): `cd backend && . .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000`. DB padrao e SQLite (`DATABASE_URL=sqlite:///./reqsys.db`); nenhum servico externo e necessario (todas as integracoes Redmine/SSRS/IA/Azure sao opcionais e default vazias).
- Frontend (`:5173`): `cd frontend && VITE_API_URL=/api npm run dev -- --host 127.0.0.1 --port 5173`. Acesse `http://127.0.0.1:5173/`.
- HMR: rodando o Vite direto (sem nginx), exporte `GATEWAY_PORT=5173`, senao o websocket de HMR tenta a porta `8081` do gateway e falha.
- Login demo: informe apenas o e-mail (ex.: `ericsonjosedossantos@tieri659.onmicrosoft.com`); o campo senha e ignorado no modo demo. O token retorna em `data.access_token`.

### Lint / testes (backend)

`ruff`, `pip-audit`, `bandit` e `pytest-cov` sao instalados no venv pelo update script (nao estao em `requirements.txt`). Comandos canonicos em "Comandos essenciais". A cobertura de testes fica ~74% (gate `--cov-fail-under=60` passa).

### Evidencia visual - telas recentes (sempre aplicar)

Quando o usuario pedir telas, ultimas implementacoes ou evidencia visual, entregar **sempre os tres**:

1. Screenshots full-screen das rotas recentes.
2. Video walkthrough navegando entre as telas.
3. Aprofundamento tecnico (PR, arquivos, APIs, limitacoes do ambiente).

Rotas canonicas atuais: `/govbi-ia`, `/segredos-status`, `/figma-github`, `/monitoramento-operacional`, `/governanca`, `/`. Login demo: `ericsonjosedossantos@tieri659.onmicrosoft.com`. Artefatos em `/opt/cursor/artifacts/`. Runbook: `docs/runbooks/evidencia-visual-telas-recentes.md`.

### Gotchas (importantes)

- `backend/reqsys.db` e um SQLite versionado; rodar o app grava nele e o deixa "modified" no git. Nao commitar essas alteracoes (ver "Seguranca e segredos").
- Nunca rode `git checkout -- backend/reqsys.db` com o backend no ar: troca o arquivo sob a conexao aberta e gera erro `attempt to write a readonly database` (HTTP 500 ao criar requisito). Se precisar restaurar o DB, reinicie o uvicorn depois.
- Bug pre-existente na `main`: o build e o runtime do frontend quebram porque `frontend/src/views/PainelIntegracaoView.vue` importa `api` como default (`import api from '../services/api'`), mas `src/services/api.js` so exporta nomeado (`export const api`). O router importa essa view estaticamente, entao a SPA nao monta e `npm run build` falha com `MISSING_EXPORT "default"`. Correcao trivial: usar `import { api } from '../services/api'` (fora do escopo de setup de ambiente).
