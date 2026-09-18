# ReqSys Enterprise API .NET/C#

Implementação inicial completa em **.NET 8 / C# 12** para evolução gradual do ReqSys a partir do backend FastAPI atual.

## Versão

- Versão do release: `3.1.0`
- Fonte canônica: `../../VERSION`
- Versionamento de assemblies: `Directory.Build.props`

## Módulos entregues

- Autenticação demo: `POST /v1/auth/login`
- Saúde: `GET /health`, `GET /healthz`, `GET /ready` e `GET /live`
- Sistema: `GET /v1/sistema/info`
- Dashboard: `GET /v1/dashboard/resumo`
- Requisitos: `GET/POST/PUT/DELETE /v1/requisitos`
- Pipeline: `POST /v1/pipeline/executar`
- Relatórios: `GET /v1/relatorios`
- Auditoria: `GET /v1/auditoria`
- Qualidade IA: `GET /v1/qualidade-ia/resumo`

## Executar localmente

```bash
cd backend-dotnet
dotnet restore ReqSys.DotNet.sln
dotnet test ReqSys.DotNet.sln
dotnet run --project src/ReqSys.Api/ReqSys.Api.csproj
```

API local padrão: `http://localhost:5000` ou a URL indicada pelo Kestrel.

## Credenciais demo

```json
{
  "email": "admin@reqsys.local",
  "senha": "admin123"
}
```

> Uso apenas demonstrativo. Não reutilize essas credenciais em ambiente compartilhado ou público.

## Docker da API

```bash
cd backend-dotnet
docker build -t reqsys-dotnet-api:3.1.0 .
docker run --rm -p 8080:8080 \
  -e ASPNETCORE_ENVIRONMENT=Production \
  -e ReqSys__CorsOrigins__0=http://localhost:8090 \
  -e ReqSys__Jwt__Issuer=reqsys \
  -e ReqSys__Jwt__Audience=reqsys-web \
  -e ReqSys__Jwt__Secret='<valor-com-32-ou-mais-caracteres>' \
  reqsys-dotnet-api:3.1.0
```

## Frontend conectado ao .NET

Na raiz do repositorio, use a stack dedicada para subir o frontend recente com a API .NET:

```bash
export REQSYS_CORS_ORIGIN_0=http://localhost:8090
export REQSYS_JWT_ISSUER=reqsys
export REQSYS_JWT_AUDIENCE=reqsys-web
export REQSYS_JWT_SECRET='<valor-com-32-ou-mais-caracteres>'
docker compose -f docker-compose.dotnet.yml up --build
```

- App via gateway: `http://localhost:8090`
- Health do gateway: `http://localhost:8090/health`
- Readiness da API via proxy: `http://localhost:8090/ready`
- Liveness da API via proxy: `http://localhost:8090/live`
- Proxy do app: `http://localhost:8090/api/health`

A API não é publicada diretamente pelo `docker-compose.dotnet.yml`; apenas o `nginx` expõe porta no host. Para diagnóstico pontual, use `docker compose exec api curl http://localhost:8080/ready` ou publique uma porta local temporária em override privado não versionado.

## Endurecimento operacional da stack .NET

- `ASPNETCORE_ENVIRONMENT` usa `Production` por padrão na imagem e no compose.
- Variáveis obrigatórias são validadas antes da subida em ambiente não Development: CORS, emissor JWT, audiência JWT e segredo JWT.
- O segredo JWT não possui valor padrão e deve ser injetado por variável/secret do ambiente de execução.
- `docker-compose.dotnet.yml` não expõe a API diretamente; o acesso externo passa pelo proxy `nginx`.
- Healthchecks usam `/ready` na API, `/` no frontend e `/health` no gateway.
- `depends_on.condition: service_healthy` reduz corrida entre API, frontend e proxy.
- Containers usam `no-new-privileges`; a API roda como usuário não root, com filesystem somente leitura e `tmpfs` para `/tmp`.
- O proxy adiciona headers de segurança, limites de taxa e rotas explícitas para readiness/liveness.

## Testes de subida recomendados

```bash
docker compose -f docker-compose.dotnet.yml config
docker compose -f docker-compose.dotnet.yml up --build -d
docker compose -f docker-compose.dotnet.yml ps
curl --fail http://localhost:8090/health
curl --fail http://localhost:8090/api/health
docker compose -f docker-compose.dotnet.yml down --remove-orphans
```

## Compatibilidade

Essa stack nao altera os `docker-compose*.yml` atuais do backend FastAPI. Ela usa `backend-dotnet/`, `frontend/` e `infra/nginx/default.dotnet.conf`.

Compatibilidade validada contra `origin/main` na versao `3.1.0`. O frontend recente consome o contrato `/api -> /v1/*`; por isso a API .NET inclui endpoints de compatibilidade para login, dashboard, requisitos, auditoria, qualidade IA, SSRS, cofre, specs e fluxo de pipeline demonstrativo.
