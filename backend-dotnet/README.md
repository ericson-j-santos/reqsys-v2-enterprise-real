# ReqSys Enterprise API .NET/C#

Implementação inicial completa em **.NET 8 / C# 12** para evolução gradual do ReqSys a partir do backend FastAPI atual.

## Versão

- Versão do release: `3.1.0`
- Fonte canônica: `../../VERSION`
- Versionamento de assemblies: `Directory.Build.props`

## Módulos entregues

- Autenticação demo: `POST /v1/auth/login`
- Saúde: `GET /health` e `GET /healthz`
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

## Docker

```bash
cd backend-dotnet
docker build -t reqsys-dotnet-api:3.1.0 .
docker run --rm -p 8080:8080 reqsys-dotnet-api:3.1.0
```
