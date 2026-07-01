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

O script automatiza:

- leitura pública de `/v1/auth/config` para Azure AD, demo login e redirect esperado;
- smoke público mínimo de `/health` e `/api/runtime/*`;
- checagem opcional da presença dos nomes de secrets obrigatórios via `fly secrets list --json`;
- artifact rastreável para anexar em PR, aprovação QA/Ops ou mudança operacional.

## Pendências críticas

| Item | Automatizável | Evidência esperada | Dono |
|---|---:|---|---|
| Redirect URI no Microsoft Entra ID | Parcial | `/v1/auth/config` deve publicar `https://reqsys-app.fly.dev/auth/callback.html`; cadastro real no portal continua humano | Operador Azure |
| Secrets produção Fly.io | Parcial | `fly secrets list --json` deve conter nomes obrigatórios; valores reais não são coletados | Operador Fly/Ops |
| Smoke público `/api/runtime/*` | Sim | `public_smoke=ok` no artifact do auditor | QA/Ops |
| Auth/CORS/JWT gates | Parcial | backend deve iniciar com `APP_ENV=production`, demo desativado e issuer/audience presentes; CORS/JWT seguem cobertos pelos testes de segurança | Segurança/Ops |
| Aprovação QA | Não | aceite funcional final registrado | QA |
| Aprovação OPS | Não | aceite operacional registrado | OPS |
| Plano de rollback | Não | runbook/release com release anterior, comando de rollback e validação pós-rollback | OPS |
| Janela de implantação | Não | janela formal aprovada | Gestão/Ops |
| Domínio corporativo | Não | DNS/TLS corporativo configurado | Infra |

## Redirect URI canônico

Para o fluxo atual com página estática de retorno, o callback canônico de produção é:

```text
https://reqsys-app.fly.dev/auth/callback.html
```

Manter também `https://reqsys-app.fly.dev` no App Registration é aceitável temporariamente para compatibilidade com bundles antigos em cache, mas a evidência de pronto deve apontar para o callback versionado.

## Critério objetivo de desbloqueio

O ambiente só deve ser tratado como produção governada quando:

1. `prod_readiness_audit` não retornar checks `blocked`.
2. A evidência humana confirmar Redirect URI no Entra ID.
3. QA e OPS registrarem aceite.
4. O plano de rollback e a janela de implantação estiverem documentados.
5. Os gates de produção de segurança permanecerem verdes no CI.
