# Levantamento automatizado — produção ReqSys/Fly.io

Status: **action_required**
Validado em: `2026-07-02T16:43:14.715239Z`
Blocked: **0** · Action required/manual: **2**

| Área | Check | Status | Humano? | Detalhe |
|---|---|---|---|---|
| auth_azure | `azure_redirect_uri` | ✅ ok | não | Callback público esperado deve estar refletido em /v1/auth/config. |
| auth_azure | `entra_redirect_uri_registered` | ✅ ok | não | Cadastro real do callback no Microsoft Entra ID deve estar presente nos redirect URIs SPA. |
| security | `auth_demo_disabled` | ✅ ok | não | Produção exige ALLOW_DEMO_LOGIN=false e demo_login_enabled=false. |
| security | `production_environment` | ✅ ok | não | Produção Fly.io deve publicar um alias produtivo em /v1/auth/config. |
| auth_azure | `azure_public_config` | ✅ ok | não | AZURE_TENANT_ID/AZURE_CLIENT_ID precisam estar configurados no backend. |
| runtime | `public_smoke` | ✅ ok | não | Smoke público mínimo aderente ao contrato versionado da API. |
| secrets | `fly_secrets_presence` | ✅ ok | não | Validação sem valores: confirma presença nominal dos secrets obrigatórios no Fly.io. |
| secrets | `fly_secrets_reviewed` | 🟡 manual | sim | Valores reais dos secrets não são coletados; revisão humana deve ser registrada. |
| governance | `governance_approvals` | 🟡 manual | sim | Aprovações, rollback e janela de implantação continuam humanos/processuais. |
| dns | `corporate_domain` | 🟢 recommended | sim | Domínio corporativo é recomendado, não bloqueante para runtime .fly.dev. |

## Evidência JSON
Arquivo pareado: `artifacts\prod-readiness-audit.json`
