# ReqSys Codex Worker Pool

Serviço local/DEV para coordenar workers Codex em múltiplos hosts sem compartilhar working tree.

## Capacidades

- registro de worker com `host`, `role`, `profile`, versão do controlador, SHA das regras e estado do Gateway;
- readiness fail-closed quando o SHA canônico esperado das regras não estiver configurado ou o worker anunciar SHA divergente;
- heartbeat e distinção entre worker ocioso, `ESTUDO`, degradado e offline;
- fila SQLite persistente com transação `BEGIN IMMEDIATE`, idempotência e aquisição exclusiva;
- lanes lógicas por repositório com `max_in_flight`, pausa (`enabled=false`) e fairness determinístico;
- afinidade opcional de worker por repositório, mantendo pool compartilhado quando não configurada;
- lease renovável e recuperação automática após timeout;
- watchdog de progresso material: heartbeat, polling e renovação de lease não reiniciam o relógio; após 900s sem avanço, a task é reroteada quando houver worker alternativo elegível ou bloqueada quando não houver;
- tentativas limitadas e quarentena/DLQ auditável;
- contrato `Builder -> produced_sha -> Validator`, impedindo autovalidação;
- task `BLOCKED_EXTERNAL` libera o worker e pode ser reenfileirada sem duplicar identidade;
- snapshot determinístico para observabilidade do pool;
- API protegida por bearer token lido de arquivo. O valor não é versionado.

## Execução local

```powershell
cd services/codex-worker-pool
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
$env:CODEX_WORKER_POOL_API_TOKEN_FILE="C:\caminho\seguro\token"
$env:CODEX_WORKER_POOL_EXPECTED_RULES_SHA="<sha-canônico-de-40-caracteres>"
$env:CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS="900"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8097
```

Linux/macOS:

```bash
CODEX_WORKER_POOL_API_TOKEN_FILE=/run/secrets/codex_worker_pool_api_token \
CODEX_WORKER_POOL_EXPECTED_RULES_SHA=<sha-canônico-de-40-caracteres> \
CODEX_WORKER_POOL_PROGRESS_STALL_SECONDS=900 \
uvicorn app.main:app --host 127.0.0.1 --port 8097
```

O `/health` fica `503/not_ready` quando o arquivo de token não está disponível ou quando `CODEX_WORKER_POOL_EXPECTED_RULES_SHA` não fixa o SHA canônico das regras.

## Testes

```bash
python -m pytest services/codex-worker-pool/tests -q
```

A suíte cobre replay idempotente, concorrência, lease expirado, quarentena, perfis `NORMAL/ESTUDO`, bloqueio externo, separação Builder/Validator, leitura independente, fairness entre repositórios, `max_in_flight`, afinidade, watchdog sem falso progresso e fluxo HTTP completo.

## PC24x7

O compose versionado na raiz (`docker-compose.pc24x7-codex-worker-pool.yml`) publica apenas em loopback (`127.0.0.1:8097`) e exige `CODEX_WORKER_POOL_API_TOKEN_FILE_HOST`.

A existência do compose **não autoriza deploy**. A materialização no PC24x7 continua sujeita ao Command Gateway, sessão governada e validação do ambiente.

## Lanes por repositório

Cada repositório entra automaticamente com uma lane habilitada e `max_in_flight=1`. A configuração pode ser ajustada pela API autenticada:

- `GET /v1/repositories`: snapshot das lanes;
- `POST /v1/repositories`: cria/atualiza `enabled` e `max_in_flight`;
- `PUT /v1/workers/{worker_id}/affinities`: substitui a lista de repositórios permitidos para o worker.

Lista de afinidades vazia significa **pool compartilhado**. Quando existe ao menos uma afinidade para o worker, claims ficam restritos à lista configurada. O scheduler usa contadores monotônicos separados para Builder e Validator, evitando starvation entre repositórios elegíveis.
