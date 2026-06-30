# Fly.io Enterprise Sync — ReqSys

## Objetivo

Consolidar a operação Fly.io em uma matriz canônica versionada, com ambientes segregados, promoção controlada, smoke test pós-deploy e evidência de governança.

## Matriz canônica

A fonte versionada é `infra/fly-environments.json` e a ordem de promoção é sempre:

```text
dev → hml → prod
```

Cada ambiente declara:

- arquivo `fly.toml` isolado;
- app Fly da API;
- URL pública da API;
- URL pública do frontend;
- volume persistente independente;
- lista de nomes de secrets obrigatórios;
- endpoints de smoke test;
- necessidade de approval gate.

## IaC por ambiente

```text
backend/
├── fly.dev.toml
├── fly.staging.toml
├── fly.toml
└── Dockerfile.fly
```

Os arquivos `infra/dev|hml|prod/fly.toml` permanecem como referência espelhada; a fonte canônica de deploy é `backend/fly.*.toml` declarada em `infra/fly-environments.json`.

Os arquivos não podem conter valores reais de segredo. Secrets devem ser definidos fora do Git com `fly secrets set` por app e ambiente.

## Pipeline canônico

O workflow `Fly Enterprise Sync` executa:

1. validação da matriz IaC com `scripts/validate_fly_enterprise_sync.py`;
2. resolução do ambiente alvo;
3. política de deploy, com confirmação textual obrigatória para produção em `workflow_dispatch`;
4. deploy com `flyctl deploy --config <backend/fly.*.toml>` e `--build-arg GITHUB_SHA`;
5. smoke test público com `scripts/validate_public_runtime.py`;
6. validação de publicação (`validate_publication_sync.py`) e login (`validar_login_multi_ambiente.py`);
7. publicação de artifacts de evidência.

### Automação em `main` (dev → hml)

A cada push em `main` que altere `backend/`, `frontend/` ou IaC Fly, o workflow dispara **automaticamente** a promoção:

```text
dev (reqsys-api-dev / reqsys-app-dev) → hml (reqsys-api-stg / reqsys-app-stg)
```

- **Produção** continua no workflow dedicado `Deploy Production Sync` (gate `APROVO-PROD` em dispatch manual).
- A ordem `max-parallel: 1` garante que homologação só deploya após desenvolvimento.
- Homologação reutiliza o skip de secrets Azure quando `AZURE_TENANT_ID`/`AZURE_CLIENT_ID` não estão no GitHub (secrets já no Fly).

### Dispatch manual

Actions → **Fly Enterprise Sync** → Run workflow:

| Campo | Uso |
|---|---|
| `target_environment` | `dev`, `hml` ou `prod` |
| `deploy` | `true` para deploy; `false` para smoke read-only |
| `approve_prod_deploy` | `APROVO-PROD` obrigatório apenas para `prod` |

## Drift detection versionado

O drift mínimo bloqueante é validado sem credenciais:

- apps e volumes únicos por ambiente;
- `APP_ENV`/`PUBLIC_ENVIRONMENT` coerente;
- health check Fly em `/health`;
- CORS sem wildcard;
- ausência de secrets materializados no TOML;
- approval obrigatório em `hml` e `prod`;
- smoke endpoints definidos.

## Rollback operacional

Rollback deve ser feito por release anterior conhecida no Fly ou por redeploy de tag/sha aprovado. Para produção, exigir change ticket, artifact de smoke e aprovação humana no environment do GitHub Actions.
