# Workflow — Configurar Fly Auth Azure

Workflow criado:

```text
.github/workflows/configurar-fly-auth-azure.yml
```

## Objetivo

Permitir configurar o login Microsoft/Azure AD no Fly.io diretamente pelo GitHub Actions, inclusive pelo celular, sem terminal local.

## Estratégia

O workflow resolve `AZURE_TENANT_ID` e `AZURE_CLIENT_ID` nesta ordem:

1. Inputs manuais do workflow, quando preenchidos.
2. Cofre ReqSys via `/v1/cofre/segredos/{key}`, quando `COFRE_API_URL` e `VAULT_API_TOKEN` estão configurados nos GitHub Secrets.
3. Falha segura, sem aplicar configuração incompleta.

## Secrets necessários no GitHub

| Secret | Obrigatório | Finalidade |
|---|---:|---|
| `FLY_API_TOKEN` | Sim | Permite executar `flyctl secrets set` |
| `COFRE_API_URL` | Opcional | URL base da API que expõe `/v1/cofre` |
| `VAULT_API_TOKEN` | Opcional | Token service-to-service para ler o cofre |

## Execução pelo GitHub no celular

1. Abrir o repositório no GitHub.
2. Ir em **Actions**.
3. Selecionar **Configurar Fly Auth Azure**.
4. Clicar em **Run workflow**.
5. Preencher:

| Campo | Valor produção |
|---|---|
| `fly_app` | `reqsys-api` |
| `app_env` | `production` |
| `app_public_url` | `https://reqsys-app.fly.dev` |
| `api_public_url` | `https://reqsys-api.fly.dev` |
| `azure_tenant_id` | deixar vazio se existir no cofre |
| `azure_client_id` | deixar vazio se existir no cofre |
| `cofre_tenant_key` | `AZURE_TENANT_ID` |
| `cofre_client_key` | `AZURE_CLIENT_ID` |

## O que o workflow executa

1. Instala `flyctl`.
2. Resolve `AZURE_TENANT_ID` e `AZURE_CLIENT_ID` por input ou cofre.
3. Aplica no Fly.io:

```bash
flyctl secrets set \
  APP_ENV=production \
  ALLOW_DEMO_LOGIN=false \
  APP_PUBLIC_URL=https://reqsys-app.fly.dev \
  API_PUBLIC_URL=https://reqsys-api.fly.dev \
  AZURE_TENANT_ID=<resolvido> \
  AZURE_CLIENT_ID=<resolvido> \
  -a reqsys-api
```

4. Valida:

```text
https://reqsys-api.fly.dev/v1/auth/config
```

## Resultado esperado

```json
{
  "success": true,
  "data": {
    "azure_enabled": true,
    "auth_status": "ready",
    "missing_fields": [],
    "expected_redirect_uri": "https://reqsys-app.fly.dev",
    "demo_login_enabled": false
  }
}
```

## Observação sobre Azure Connector

Neste ambiente de chat não há conector Azure disponível. Por isso, a alternativa segura é:

- usar o cofre ReqSys se ele já tiver as chaves;
- ou informar `AZURE_TENANT_ID` e `AZURE_CLIENT_ID` como inputs no workflow;
- e manter o segredo sensível `FLY_API_TOKEN` apenas em GitHub Secrets.

## Gates

O PR não deve sair de draft até:

| Gate | Status esperado |
|---|---|
| Workflow de configuração | Sucesso |
| `/v1/auth/config` | `auth_status=ready` |
| Redirect URI no Entra ID | Registrado |
| Login E2E manual/anônimo | Sucesso |
| Evidência | Artefato anexado ao PR |
