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
| `scripts/` | Automação local, publicação, validação e tarefas auxiliares. |

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

### Execução local sem Docker

Para subir o stack diretamente (Python 3.12+, Node.js 20+, nginx instalados):

```bash
bash scripts/executar-local.sh
```

No Windows PowerShell, usar o equivalente:

```powershell
./scripts/executar-local.ps1
```

### E2E e validações no nível raiz

A raiz do repositório expõe scripts npm para execução agregada:

```bash
npm ci
npm run test:e2e          # Playwright via playwright.config.ts
npm run test:e2e:ui       # modo UI interativo
npm run test:e2e:report   # abrir relatório anterior
npm run validate:access   # node scripts/validar-acessos-publicos.mjs
```

Validação agregada de qualidade (backend + builds + E2E):

```bash
bash scripts/validar_qualidade.sh
```

Smoke test rápido contra URLs publicadas:

```bash
bash scripts/testar_urls_ambiente.sh dev
bash scripts/testar_urls_ambiente.sh hml
bash scripts/testar_urls_ambiente.sh prod
```

Para o frontend principal há um runner E2E protegido por verificação de readiness:

```bash
cd frontend
npm run test:e2e:stable
```

### Gates de segurança individuais

Quando alterar autenticação, JWT, CORS ou gates de produção, executar a bateria isolada:

```bash
bash scripts/run_security_gate_tests.sh
```

No Windows PowerShell, usar `scripts/run_security_gate_tests.ps1`.

## CI obrigatório

Antes de merge em `main`, validar o workflow `CI — ReqSys v2 Enterprise` com os jobs:

| Job | Gate esperado |
| --- | --- |
| `Backend Lint & Security (ruff + pip-audit + bandit)` | `success` |
| `Backend Tests + Coverage (pytest)` | `success` com cobertura mínima configurada |
| `Frontend Build + Security Audit (Vite + npm audit)` | `success` |
| `Frontend Responsive E2E (Playwright)` | `success` |

Não considerar um PR pronto para merge quando o E2E responsivo estiver ausente, em execução ou falho, salvo decisão técnica formal e documentada.

Workflows complementares no diretório `.github/workflows/`:

| Workflow | Disparo | Função |
| --- | --- | --- |
| `validacao-acessos.yml` | push em `main`, agendado (`cron: 17 10 * * *`) e `workflow_dispatch` | Executa `node scripts/validar-acessos-publicos.mjs` e publica artifact `validacao-acessos-publicos`. |
| `validar-painel-ciclo.yml` | PRs em `docs/painel-ciclo-completo-reqsys.html`, `docs/ciclo-completo/**`, `scripts/validar_painel_ciclo.py` ou no próprio workflow, e `workflow_dispatch` | Executa `python scripts/validar_painel_ciclo.py` e publica artifact `reqsys-painel-ciclo-completo`. |

O job `Backend Tests + Coverage (pytest)` também executa verificação anti-mojibake em `app/api/` e `app/services/`. Não introduzir strings com encoding quebrado nesses diretórios.

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