# REQSYS#325 — Runtime Public Access + Smoke Validation + Ops Readiness

## Objetivo

Consolidar uma validação read-only para ambientes públicos Fly.io/DuckDNS, gerando evidência navegável e artifacts operacionais sem acessar secrets e sem alterar produção.

## Artifacts

O smoke validator gera dois arquivos:

- `public-runtime-validation.json`: resultado detalhado por endpoint, status HTTP, tempo de resposta, CORS básico e marcadores de frontend/runtime/login/incidentes.
- `ops-readiness-report.json`: resumo executivo com `environment`, `reachable`, `response_time`, `dashboard_ready`, `login_ready`, `api_ready`, `runtime_ready`, `evidence_ready`, `operational_status`, `readiness_percent`, `blocking_issues` e `next_actions`.

## Execução local read-only

```bash
python scripts/validate_public_runtime.py \
  --base-url https://reqsys-api.fly.dev \
  --environment prod \
  --include-optional-evidence \
  --output artifacts/runtime/public-runtime-validation.json \
  --readiness-output artifacts/runtime/ops-readiness-report.json
```

## Classificação operacional

| Status | Critério resumido |
| --- | --- |
| `unavailable` | Nenhum endpoint validado respondeu com sucesso. |
| `degraded` | Ambiente responde, mas não cumpre o contrato mínimo de API/readiness. |
| `partial` | APIs mínimas respondem, porém dashboard/evidência pública ainda não está completo. |
| `healthy` | Contrato mínimo e dashboard público estão disponíveis com readiness consolidado. |

## Dashboard operacional

O Ops Dashboard passa a exibir:

- cards de readiness público;
- status visual Fly/DuckDNS;
- sinais de API, runtime, dashboard e login;
- blocking issues do smoke público;
- timeline operacional, incident summary, risk summary e environment drift summary publicados pelo runtime dashboard.

## Governança

- O workflow `Public Runtime Evidence Gate` executa somente chamadas HTTP read-only.
- O gate não envia credenciais, tokens, cookies ou payloads de escrita.
- O modo strict continua falhando apenas pelo contrato obrigatório; evidências opcionais enriquecem os artifacts e o dashboard.
