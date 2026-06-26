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
infra/
├── dev/fly.toml
├── hml/fly.toml
└── prod/fly.toml
```

Os arquivos não podem conter valores reais de segredo. Secrets devem ser definidos fora do Git com `fly secrets set` por app e ambiente.

## Pipeline canônico

O workflow `Fly Enterprise Sync` executa:

1. validação da matriz IaC com `scripts/validate_fly_enterprise_sync.py`;
2. resolução do ambiente alvo;
3. política de deploy, com confirmação textual obrigatória para produção;
4. deploy opcional com `flyctl deploy --config <infra/env/fly.toml>`;
5. smoke test público com `scripts/validate_public_runtime.py`;
6. publicação de artifacts de evidência.

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
