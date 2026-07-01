# Levantamento de pendências — produção ReqSys no Fly.io

Este runbook consolida as pendências críticas de produção e separa o que pode ser automatizado do que permanece humano/processual.

## Automação entregue

Use o auditor versionado para gerar evidência JSON e Markdown sem expor valores de segredos:

```bash
python scripts/prod_readiness_audit.py \
  --api-url https://reqsys-api.fly.dev \
  --app-url https://reqsys-app.fly.dev \
  --output artifacts/prod-readiness-audit.json \
  --markdown-output artifacts/prod-readiness-audit.md
```

Para validar somente a presença nominal dos secrets no Fly.io, sem imprimir valores:

```bash
python scripts/prod_readiness_audit.py --check-fly --fly-app reqsys-api
```

Para anexar evidência humana/processual ao mesmo artifact:

```bash
python scripts/prod_readiness_audit.py \
  --check-fly \
  --fly-app reqsys-api \
  --human-evidence artifacts/prod-readiness-human-evidence.json \
  --output artifacts/prod-readiness-audit.json \
  --markdown-output artifacts/prod-readiness-audit.md
```

O script automatiza:

- leitura pública de `/v1/auth/config` para Azure AD, demo login, ambiente e redirect esperado;
- smoke público mínimo aderente ao contrato versionado: `/health`, `/api/runtime/health`, `/api/runtime/readiness`, `/api/runtime/liveness` e `/v1/auth/config`;
- checagem opcional da presença dos nomes de secrets obrigatórios via `fly secrets list --json`;
- artifact rastreável para anexar em PR, aprovação QA/Ops ou mudança operacional;
- ingestão opcional de evidência humana sem coletar valores reais de secrets.

## Pendências críticas

| Item | Automatizável | Evidência esperada | Dono |
|---|---:|---|---|
| Redirect URI publicado pela API | Sim | `/v1/auth/config` deve publicar `https://reqsys-app.fly.dev/auth/callback.html` | Backend/Ops |
| Redirect URI registrado no Microsoft Entra ID | Parcial | `prod-readiness-human-evidence.json` deve registrar `entra_redirect_uri_registered.status=confirmed` | Operador Azure |
| Secrets produção Fly.io — presença nominal | Parcial | `fly secrets list --json` deve conter nomes obrigatórios; valores reais não são coletados | Operador Fly/Ops |
| Secrets produção Fly.io — valores reais revisados | Não | `prod-readiness-human-evidence.json` deve registrar `fly_secrets_reviewed.status=confirmed` | Operador Fly/Ops |
| Smoke público `/api/runtime/*` | Sim | `public_smoke=ok` no artifact do auditor | QA/Ops |
| Auth/CORS/JWT gates | Parcial | backend deve iniciar com `APP_ENV=production`, demo desativado e issuer/audience presentes; CORS/JWT seguem cobertos pelos testes de segurança | Segurança/Ops |
| Aprovação QA | Não | `qa_approval.status=approved` | QA |
| Aprovação OPS | Não | `ops_approval.status=approved` | OPS |
| Plano de rollback | Não | `rollback_plan_documented.status=confirmed` | OPS |
| Janela de implantação | Não | `deployment_window_approved.status=approved` | Gestão/Ops |
| Domínio corporativo | Não | DNS/TLS corporativo configurado | Infra |

## Redirect URI canônico

Para o fluxo atual com página estática de retorno, o callback canônico de produção é:

```text
https://reqsys-app.fly.dev/auth/callback.html
```

Manter também `https://reqsys-app.fly.dev` no App Registration é aceitável temporariamente para compatibilidade com bundles antigos em cache, mas a evidência de pronto deve apontar para o callback versionado.

## Secrets mínimos esperados no Fly.io

```bash
fly secrets set \
  APP_ENV=production \
  ALLOW_DEMO_LOGIN=false \
  JWT_SECRET='<valor-forte-minimo-32-caracteres>' \
  JWT_ISSUER=reqsys-api \
  JWT_AUDIENCE=reqsys-users \
  APP_PUBLIC_URL=https://reqsys-app.fly.dev \
  API_PUBLIC_URL=https://reqsys-api.fly.dev \
  AZURE_TENANT_ID='<tenant-id>' \
  AZURE_CLIENT_ID='<client-id>' \
  --app reqsys-api
```

O auditor valida somente a presença nominal dos secrets quando executado com `--check-fly`; ele não lê, imprime nem persiste valores sensíveis.

## Evidência humana esperada

Use o template versionado em:

```text
docs/runbooks/prod-readiness-human-evidence.template.json
```

Copie para:

```text
artifacts/prod-readiness-human-evidence.json
```

Preencha somente metadados não sensíveis, como responsável, data, link do ticket/change e status. Não registre valores de secrets.

## Critério objetivo de desbloqueio

O ambiente só deve ser tratado como produção governada quando:

1. `prod_readiness_audit` não retornar checks `blocked`.
2. A evidência humana confirmar Redirect URI no Entra ID.
3. A presença nominal e a revisão humana dos secrets Fly.io estiverem evidenciadas.
4. QA e OPS registrarem aceite.
5. O plano de rollback e a janela de implantação estiverem documentados.
6. Os gates de produção de segurança permanecerem verdes no CI.
