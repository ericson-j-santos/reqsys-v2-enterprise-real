# AGENTS.md

Guia operacional canÃ´nico para agentes, automaÃ§Ãµes e assistentes que atuam neste repositÃ³rio. Mantenha este arquivo objetivo, rastreÃ¡vel e alinhado ao estado real do cÃ³digo.

## PrincÃ­pios de trabalho

- Priorizar mudanÃ§as pequenas, revisÃ¡veis e com escopo explÃ­cito.
- NÃ£o executar aÃ§Ãµes destrutivas sem evidÃªncia, justificativa e possibilidade de rollback.
- NÃ£o commitar segredos, `.env`, bancos locais, artefatos de build, logs sensÃ­veis ou arquivos temporÃ¡rios.
- Preferir documentaÃ§Ã£o em portuguÃªs do Brasil quando o conteÃºdo for operacional ou de produto.
- Validar comandos antes de documentÃ¡-los. Quando houver dÃºvida, registrar como pendÃªncia em vez de assumir.

## Estrutura principal

| Caminho | Responsabilidade |
| --- | --- |
| `backend/` | API principal FastAPI, domÃ­nio, serviÃ§os, integraÃ§Ãµes e testes Python. |
| `frontend/` | Frontend principal Vue/Vite/Vuetify. |
| `backend-dotnet/` | ServiÃ§o .NET complementar, quando aplicÃ¡vel. |
| `frontend-angular/` | Frente Angular complementar ou experimental. |
| `frontend-vuetify/` | Variante Vuetify usada em validaÃ§Ãµes especÃ­ficas. |
| `e2e/` e `frontend/tests/e2e/` | Testes Playwright e validaÃ§Ãµes responsivas. |
| `.github/workflows/` | CI, quality gates e validaÃ§Ãµes agendadas/manuais. |
| `docs/` | DecisÃµes, runbooks, evidÃªncias e documentaÃ§Ã£o operacional. |
| `scripts/` | AutomaÃ§Ã£o local, publicaÃ§Ã£o, validaÃ§Ã£o e tarefas auxiliares. |

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

### Qualidade e seguranÃ§a backend

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

### Docker e publicaÃ§Ã£o local

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

## CI obrigatÃ³rio

Antes de merge em `main`, validar o workflow `CI â€” ReqSys v2 Enterprise` com os jobs:

| Job | Gate esperado |
| --- | --- |
| `Backend Lint & Security (ruff + pip-audit + bandit)` | `success` |
| `Backend Tests + Coverage (pytest)` | `success` com cobertura mÃ­nima configurada |
| `Frontend Build + Security Audit (Vite + npm audit)` | `success` |
| `Frontend Responsive E2E (Playwright)` | `success` |

NÃ£o considerar um PR pronto para merge quando o E2E responsivo estiver ausente, em execuÃ§Ã£o ou falho, salvo decisÃ£o tÃ©cnica formal e documentada.

## Gates de produÃ§Ã£o

ProduÃ§Ã£o deve ser bloqueada se qualquer condiÃ§Ã£o abaixo ocorrer:

- `APP_ENV` produtivo com `ALLOW_DEMO_LOGIN=true`.
- `CORS_ORIGINS=*`.
- `JWT_SECRET` fraco, ausente ou padrÃ£o.
- `JWT_ISSUER` ausente.
- `JWT_AUDIENCE` ausente.
- `JWT_EXP_MINUTES <= 0`.
- Logs contendo token, senha, CPF, PII, connection string ou segredo.
- Auditoria sem `correlation_id`.
- Endpoint administrativo de conector exposto sem autorizaÃ§Ã£o adequada.

## Deploy de hotfix e ambientes

- Quando houver mudanÃ§as locais fora do escopo do hotfix, publicar a partir de uma Ã¡rvore limpa contendo somente os arquivos do ajuste aprovado.
- Para mudanÃ§as de frontend/autenticaÃ§Ã£o, validar localmente com `npm run build` e teste unitÃ¡rio ou regressivo focado antes de publicar.
- Promover ambientes em ordem: `dev` primeiro, depois `staging`, depois `prod`.
- ApÃ³s cada publicaÃ§Ã£o, validar o endpoint afetado no ambiente publicado antes de seguir para o prÃ³ximo.
- NÃ£o publicar produÃ§Ã£o quando o deploy puder carregar alteraÃ§Ãµes locais nÃ£o revisadas ou nÃ£o relacionadas.

## PadrÃ£o de PR

Cada PR deve conter:

- Resumo objetivo.
- Escopo e fora de escopo.
- EvidÃªncias de teste.
- Riscos e rollback quando aplicÃ¡vel.
- ReferÃªncia a issue, decisÃ£o tÃ©cnica ou release note quando existir.

CritÃ©rios mÃ­nimos para merge:

- PR nÃ£o estÃ¡ em draft.
- Branch estÃ¡ mergeÃ¡vel.
- CI completo e verde.
- ComentÃ¡rios crÃ­ticos resolvidos.
- Sem mudanÃ§as fora do escopo declarado.

## PadrÃ£o de commits

Usar commits claros e preferencialmente convencionais:

```text
feat: adicionar recurso
fix: corrigir comportamento
test: adicionar cobertura
docs: atualizar documentaÃ§Ã£o
ci: ajustar pipeline
chore: manutenÃ§Ã£o sem impacto funcional
```

## SeguranÃ§a e segredos

- Nunca registrar valores reais de segredo em documentaÃ§Ã£o, teste ou log.
- Usar placeholders seguros como `placeholder`, `example.com`, `reqsys-ci` ou equivalentes.
- NÃ£o commitar `.env`, bancos SQLite locais, dumps, prints com PII ou artefatos de execuÃ§Ã£o.
- Antes de publicar cÃ³digo que toque autenticaÃ§Ã£o, CORS, JWT, conectores ou permissÃµes, validar gates individuais e testes regressivos.

## Correlation ID e auditoria

Toda operaÃ§Ã£o relevante deve preservar rastreabilidade:

- Aceitar `X-Correlation-ID` ou `X-Request-ID` quando aplicÃ¡vel.
- Propagar o identificador para serviÃ§os internos, logs, envelopes e auditoria.
- Gerar identificador quando o cliente nÃ£o enviar.
- NÃ£o mascarar o `correlation_id`, mas mascarar PII e segredos.

## DocumentaÃ§Ã£o esperada

Para mudanÃ§as relevantes, atualizar pelo menos um dos itens abaixo:

- `README.md`, quando afetar uso geral.
- `docs/`, quando afetar arquitetura, seguranÃ§a, operaÃ§Ã£o ou runbook.
- Release note em `docs/releases/`, quando houver entrega significativa.
- Matriz de testes, quando novos gates ou cenÃ¡rios crÃ­ticos forem adicionados.

## OrientaÃ§Ãµes para agentes

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
- NÃ£o criar mÃºltiplos PRs concorrentes para o mesmo arquivo sem necessidade.
- Quando houver PRs duplicados, consolidar o conteÃºdo canÃ´nico em um Ãºnico PR e fechar os demais com justificativa.
- Preferir alteraÃ§Ã£o mÃ­nima em arquivos existentes.
- NÃ£o fazer merge em lote de PRs antigos sem revalidar contra a `main` atual.
- NÃ£o depender de revisÃ£o automÃ¡tica como Ãºnica evidÃªncia. CI e inspeÃ§Ã£o tÃ©cnica continuam obrigatÃ³rios.

## DecisÃ£o canÃ´nica atual

O ciclo de PRs deve seguir este fluxo:

```text
triagem â†’ ajuste mÃ­nimo â†’ CI completo â†’ evidÃªncia â†’ merge controlado â†’ validaÃ§Ã£o pÃ³s-merge â†’ fechamento de duplicados
```

Este arquivo Ã© a referÃªncia operacional para prÃ³ximos agentes que atuarem no repositÃ³rio.

## Cursor Cloud specific instructions

Ambiente jÃ¡ inicializado pelo update script (venv do backend + `npm ci` no frontend). Dependencias de sistema (`unixodbc`/`unixodbc-dev` para `pyodbc` e `python3.12-venv`) ja estao no snapshot da VM; nao precisam ser reinstaladas.

### Coordenador Principal (operacao hibrida)

Automacao real fica em GitHub Actions + scripts + agentes por PR; chats fixos sao contexto, nao runtime autonomo. Menu fechado: `docs/runbooks/coordenador-principal-menu-operacional.md`. Leitura preferencial: artifact `coordenador-status-evidence` via workflow **Coordenador Status Consolidator**.

**Hub documentacao Padrão Ouro Tier 1:** `docs/padrao-ouro/README.md` — Living Architecture Index, ADR Index, Runtime Evidence Graph, Contract Catalog e Engineering Playbooks. Indice machine-readable para agentes: `docs/padrao-ouro/living-architecture-index.json`.

**Gate obrigatorio para nova frente:** `python scripts/agent_increment_gate.py --increment-type new_front --intent "<objetivo>"`. Exit code `0` = permitido; `1` = bloqueado (seguir `recommended_actions`). Campo `increment_gate.new_front_allowed` em `coordenador-status.json`.

### Servicos canonicos (modo dev, sem Docker)

A forma mais leve de rodar o produto e backend uvicorn + frontend Vite (o Vite faz proxy de `/api` para o backend, conforme `frontend/vite.config.js`). Nginx/KB/Docker nao sao necessarios para o fluxo principal.

- Backend (`:8000`): `cd backend && . .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000`. DB padrao e SQLite (`DATABASE_URL=sqlite:///./reqsys.db`); nenhum servico externo e necessario (todas as integracoes Redmine/SSRS/IA/Azure sao opcionais e default vazias).
- Frontend (`:5173`): `cd frontend && VITE_API_URL=/api npm run dev -- --host 127.0.0.1 --port 5173`. Acesse `http://127.0.0.1:5173/`.
- HMR: rodando o Vite direto (sem nginx), exporte `GATEWAY_PORT=5173`, senao o websocket de HMR tenta a porta `8081` do gateway e falha.
- Login demo: informe apenas o e-mail (ex.: `ericsonjosedossantos@tieri659.onmicrosoft.com`); o campo senha e ignorado no modo demo. O token retorna em `data.access_token`.

### Lint / testes (backend)

`ruff`, `pip-audit`, `bandit` e `pytest-cov` sao instalados no venv pelo update script (nao estao em `requirements.txt`). Comandos canonicos em "Comandos essenciais". A cobertura de testes fica ~74% (gate `--cov-fail-under=60` passa).

### Gotchas (importantes)

- `backend/reqsys.db` e um SQLite versionado; rodar o app grava nele e o deixa "modified" no git. Nao commitar essas alteracoes (ver "Seguranca e segredos").
- Nunca rode `git checkout -- backend/reqsys.db` com o backend no ar: troca o arquivo sob a conexao aberta e gera erro `attempt to write a readonly database` (HTTP 500 ao criar requisito). Se precisar restaurar o DB, reinicie o uvicorn depois.
- Bug pre-existente na `main`: o build e o runtime do frontend quebram porque `frontend/src/views/PainelIntegracaoView.vue` importa `api` como default (`import api from '../services/api'`), mas `src/services/api.js` so exporta nomeado (`export const api`). O router importa essa view estaticamente, entao a SPA nao monta e `npm run build` falha com `MISSING_EXPORT "default"`. Correcao trivial: usar `import { api } from '../services/api'` (fora do escopo de setup de ambiente).
