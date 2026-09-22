# Ciclo único de requisito — Incremento 1

## Objetivo

Criar um caminho rastreável e idempotente do requisito até a implantação:

```text
ReqSys -> Redmine -> GitHub Issue -> PR -> commit -> DEV -> STAGING -> PROD -> ReqSys
```

O ReqSys é a fonte canônica do requisito e o consolidador de evidências. Redmine e GitHub continuam responsáveis por suas especialidades; não há sincronização bidirecional indiscriminada de todos os campos.

## Responsabilidades

| Informação | Sistema proprietário |
|---|---|
| requisito, critérios, prioridade | ReqSys |
| execução operacional | Redmine |
| código, Issue, branch, PR, commit | GitHub |
| implantação | pipeline/plataforma de deploy |
| evidência consolidada | ReqSys |

## Persistência

O Incremento 1 reutiliza `vinculos_git`, sem migração de banco.

Combinações usadas:

| provedor | tipo | finalidade |
|---|---|---|
| `redmine` | `issue` | Issue principal de execução |
| `github` | `issue` | Issue técnica do requisito |
| `github` | `branch` | branch vinculada |
| `github` | `pr` | Pull Request |
| `github` | `commit` | commit/merge integrado |
| `deployment` | `deploy` | implantação por ambiente |

`ambiente` aceita `dev`, `staging` e `prod` para evidências de deploy.

## Início do ciclo

Endpoint:

```http
POST /v1/requisitos/lifecycle/{requisito_id}/iniciar
Authorization: Bearer <JWT admin>
```

ou:

```http
X-Service-Token: <token com lifecycle:write>
```

Payload opcional:

```json
{
  "github_repo": "ericson-j-santos/reqsys-v2-enterprise-real",
  "redmine_project_id": 1,
  "tracker_id": 1,
  "priority_id": 2
}
```

Comportamento:

1. procura vínculo Redmine existente;
2. cria Issue Redmine apenas quando não há vínculo;
3. persiste o vínculo antes de avançar;
4. procura vínculo GitHub Issue existente;
5. pesquisa Issue GitHub pelo código canônico antes de criar;
6. cria a Issue GitHub quando necessário;
7. consolida o estado do ciclo no ReqSys.

O código canônico (`REQ-#########`) permanece no título da Issue GitHub.

## Consulta do estado

Por ID:

```http
GET /v1/requisitos/lifecycle/{requisito_id}
X-Service-Token: <token com lifecycle:read>
```

Por código:

```http
GET /v1/requisitos/lifecycle/codigo/REQ-123456789
X-Service-Token: <token com lifecycle:read>
```

Resposta consolida:

- Redmine;
- GitHub Issue;
- PR;
- commit;
- deploy DEV;
- deploy STAGING;
- deploy PROD;
- percentual de progresso;
- `ready_for_explicit_completion`.

## Registro de evidência

```http
POST /v1/requisitos/lifecycle/codigo/REQ-123456789/evidencias
X-Service-Token: <token com lifecycle:write>
X-Correlation-Id: <correlation-id>
Content-Type: application/json
```

Exemplo PR:

```json
{
  "provedor": "github",
  "tipo": "pr",
  "repo": "ericson-j-santos/reqsys-v2-enterprise-real",
  "referencia": "1512",
  "url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/1512",
  "titulo": "Entrega REQ-123456789",
  "ambiente": null
}
```

Exemplo deploy:

```json
{
  "provedor": "fly",
  "tipo": "deploy",
  "repo": "reqsys-api",
  "referencia": "<sha-ou-deploy-id>",
  "url": "https://reqsys-api.fly.dev/health",
  "titulo": "Deploy PROD validado",
  "ambiente": "prod"
}
```

Para `tipo=deploy`, o backend normaliza o provedor persistido para `deployment`.

## GitHub Actions

Workflow:

```text
.github/workflows/requirement-lifecycle-evidence.yml
```

### Pull Requests

Em `opened`, `reopened`, `synchronize` e `closed`, o workflow procura `REQ-#########` em:

1. título da PR;
2. corpo da PR;
3. nome da branch.

Quando encontra o código, registra a PR. Se a PR foi mergeada, também registra o commit de merge.

### Deploy

O mesmo workflow aceita `workflow_call` e `workflow_dispatch`. Pipelines de implantação podem chamá-lo depois do smoke test aprovado, passando:

- `requirement_code`;
- `evidence_type=deploy`;
- `environment`;
- `reference`;
- `evidence_url`;
- `title`.

Assim a evidência é registrada somente depois da validação real do ambiente.

## Configuração necessária

Variável GitHub:

```text
REQSYS_API_BASE_URL=https://reqsys-api-dev.fly.dev
```

Secret GitHub:

```text
REQSYS_LIFECYCLE_SERVICE_TOKEN=<token escopado>
```

O token deve possuir:

```text
lifecycle:read
lifecycle:write
```

O token nunca deve ser colocado no repositório, artefato ou log.

## Cliente CI reutilizável

```bash
python scripts/register_lifecycle_evidence.py \
  --requirement-code REQ-123456789 \
  --type deploy \
  --repo reqsys-api \
  --reference "$GITHUB_SHA" \
  --environment dev \
  --url https://reqsys-api-dev.fly.dev/health \
  --output lifecycle-evidence.json
```

O script suporta:

- configuração por ambiente;
- retentativas controladas;
- tratamento distinto de erro 4xx;
- `X-Correlation-Id`;
- `--dry-run`;
- evidência JSON de execução;
- nenhuma impressão do token.

## Idempotência

A reexecução do início do ciclo:

- reutiliza vínculos Redmine/GitHub persistidos;
- pesquisa a Issue GitHub pelo código antes de criar;
- não duplica evidências com mesma combinação de requisito, provedor, tipo, referência e ambiente.

## Regra de fechamento

Deploy em PROD **não conclui automaticamente o requisito**.

Ele apenas muda `ready_for_explicit_completion` para `true`. O fechamento continua exigindo a ação explícita já existente no ReqSys, com evidência objetiva. Isso evita conclusão por inferência.

## Critério de aceite técnico

```bash
cd backend
PYTHONPATH=. pytest -q tests/test_lifecycle_orchestrator.py
```

A PR do Incremento 1 só deve ser integrada após os checks obrigatórios do repositório passarem.
