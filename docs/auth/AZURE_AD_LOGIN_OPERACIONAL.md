# Configuração operacional — Login Microsoft / Azure AD

Este documento define a configuração mínima para o login Microsoft do ReqSys funcionar em homologação e produção.

## Ambientes oficiais

| Ambiente | Frontend | API | Redirect URI esperado |
|---|---|---|---|
| Produção | `https://reqsys-app.fly.dev` | `https://reqsys-api.fly.dev` | `https://reqsys-app.fly.dev/auth/callback.html` |
| Homologação | `https://reqsys-app-stg.fly.dev` | `https://reqsys-api-stg.fly.dev` | `https://reqsys-app-stg.fly.dev/auth/callback.html` |
| Homologação legada | `https://reqsys-web-stg.fly.dev` | `https://reqsys-api-stg.fly.dev` | `https://reqsys-web-stg.fly.dev/auth/callback.html` |
| Desenvolvimento | `https://reqsys-app-dev.fly.dev` | `https://reqsys-api-dev.fly.dev` | `https://reqsys-app-dev.fly.dev/auth/callback.html` |

## Variáveis obrigatórias

| Variável | Onde configurar | Observação |
|---|---|---|
| `AZURE_TENANT_ID` | API/backend | ID do tenant Microsoft Entra ID |
| `AZURE_CLIENT_ID` | API/backend | Application/client ID do App Registration SPA |
| `APP_PUBLIC_URL` | API/backend | Origem pública do frontend, sem caminho adicional |
| `API_PUBLIC_URL` | API/backend | Origem pública da API |
| `ALLOW_DEMO_LOGIN` | API/backend | `false` em produção |
| `APP_ENV` | API/backend | `production`, `staging` ou `development` |

`AZURE_CLIENT_SECRET` não deve ser necessário para o fluxo SPA `loginRedirect + id_token`. Caso exista uso futuro de code exchange confidencial, deve ser tratado como segredo e nunca exposto no frontend.

## Configuração no Microsoft Entra ID

No App Registration usado pelo ReqSys:

1. Acesse **Authentication**.
2. Adicione a plataforma **Single-page application (SPA)**.
3. Registre exatamente as Redirect URIs abaixo, conforme ambientes usados:
   - `https://reqsys-app.fly.dev/auth/callback.html`
   - `https://reqsys-app.fly.dev`
   - `https://reqsys-app-stg.fly.dev/auth/callback.html`
   - `https://reqsys-web-stg.fly.dev/auth/callback.html`
   - `https://reqsys-app-dev.fly.dev/auth/callback.html`
   - `http://localhost:5173`
   - `http://localhost:8084`
4. Registre `/auth/callback.html` como callback principal do fluxo MSAL/PKCE. Manter também a origem pública sem caminho em produção é aceito como compatibilidade operacional enquanto bundles antigos expiram em cache.
5. Em **ID tokens**, permita emissão de `id_token` se a configuração do tenant exigir.
6. Salve e aguarde propagação.

## Configuração no Fly.io

Executar no terminal autenticado no Fly.io, substituindo os valores reais:

```bash
fly secrets set \
  APP_ENV=production \
  ALLOW_DEMO_LOGIN=false \
  APP_PUBLIC_URL=https://reqsys-app.fly.dev \
  API_PUBLIC_URL=https://reqsys-api.fly.dev \
  AZURE_TENANT_ID=<tenant-id> \
  AZURE_CLIENT_ID=<client-id> \
  -a reqsys-api
```

Para homologação atual:

```bash
fly secrets set \
  APP_ENV=staging \
  ALLOW_DEMO_LOGIN=false \
  APP_PUBLIC_URL=https://reqsys-app-stg.fly.dev \
  API_PUBLIC_URL=https://reqsys-api-stg.fly.dev \
  AZURE_TENANT_ID=<tenant-id> \
  AZURE_CLIENT_ID=<client-id> \
  -a reqsys-api-stg
```

Para homologação legada, se ainda houver tráfego ativo em `reqsys-web-stg`:

```bash
fly secrets set \
  APP_ENV=staging \
  ALLOW_DEMO_LOGIN=false \
  APP_PUBLIC_URL=https://reqsys-web-stg.fly.dev \
  API_PUBLIC_URL=https://reqsys-api-stg.fly.dev \
  AZURE_TENANT_ID=<tenant-id> \
  AZURE_CLIENT_ID=<client-id> \
  -a reqsys-api-stg
```

## Validação objetiva

Após deploy/restart da API:

```bash
curl -s https://reqsys-api.fly.dev/v1/auth/config
```

Resultado esperado:

```json
{
  "success": true,
  "data": {
    "azure_enabled": true,
    "auth_status": "ready",
    "missing_fields": [],
    "expected_redirect_uri": "https://reqsys-app.fly.dev/auth/callback.html",
    "demo_login_enabled": false
  }
}
```

Para STG:

```bash
curl -s https://reqsys-api-stg.fly.dev/v1/auth/config
```

Resultado esperado para homologação atual:

```json
{
  "success": true,
  "data": {
    "azure_enabled": true,
    "auth_status": "ready",
    "missing_fields": [],
    "expected_redirect_uri": "https://reqsys-app-stg.fly.dev/auth/callback.html",
    "demo_login_enabled": false
  }
}
```

## Correção objetiva para AADSTS50011

Erro típico:

```text
AADSTS50011: The redirect URI 'https://reqsys-app-stg.fly.dev/auth/callback.html' specified in the request does not match the redirect URIs configured for the application.
```

Ação esperada:

1. Confirmar que o frontend publicado usa bundle posterior à correção que envia `redirect_uri=https://reqsys-app-stg.fly.dev/auth/callback.html`.
2. Confirmar que `APP_PUBLIC_URL=https://reqsys-app-stg.fly.dev` está aplicado na API STG.
3. Confirmar que `https://reqsys-app-stg.fly.dev/auth/callback.html` está registrado no Microsoft Entra ID como SPA Redirect URI.
4. Limpar cache do navegador ou testar em janela anônima.
5. Reexecutar login Microsoft.

## Critério de pronto

O login só pode ser considerado corrigido quando houver evidência de:

| Critério | Resultado esperado |
|---|---|
| `/v1/auth/config` | `azure_enabled=true` |
| Produção sem demo | `demo_login_enabled=false` |
| Redirect URI | Callback `/auth/callback.html` registrado no Entra ID |
| Botão Microsoft | Visível na tela de login |
| Login em janela anônima | Retorna sessão e redireciona para aplicação |
| Logs | Sem token, senha, CPF, PII sensível ou connection string |

## Rollback seguro

Se a configuração causar erro operacional:

1. Não reabilitar login demo em produção.
2. Corrigir variáveis `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` e Redirect URI.
3. Reiniciar a API.
4. Validar `/v1/auth/config` novamente.
