# Padrão ouro de ambientes — Fly.io + DuckDNS

Este runbook define o baseline operacional dos ambientes ReqSys em Fly.io com URLs públicas Fly e aliases DuckDNS. O objetivo é manter desenvolvimento, staging e produção sempre rastreáveis, segregados e validáveis.

## Matriz canônica

| Ambiente | App Fly frontend | App Fly API | URL Fly | URL DuckDNS | Config backend | Config frontend | Volume |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dev | `reqsys-app-dev` | `reqsys-api-dev` | `https://reqsys-app-dev.fly.dev` | `https://tieridev.duckdns.org` | `backend/fly.dev.toml` | `frontend/fly.dev.toml` | `reqsys_data_dev` |
| Staging | `reqsys-app-stg` | `reqsys-api-stg` | `https://reqsys-app-stg.fly.dev` | `https://tierin.duckdns.org` | `backend/fly.staging.toml` | `frontend/fly.staging.toml` | `reqsys_data_stg` |
| Produção | `reqsys-app` | `reqsys-api` | `https://reqsys-app.fly.dev` | `https://tieriprod.duckdns.org` | `backend/fly.toml` | `frontend/fly.toml` | `reqsys_data` |

## Regras de configuração

- Cada ambiente deve usar um app Fly e um volume persistente próprios.
- Produção deve declarar `APP_ENV=production` e passar pelos gates de segurança do backend.
- `CORS_ORIGINS` deve conter apenas origens explícitas: domínio Fly do frontend, alias DuckDNS do ambiente e, quando necessário para suporte operacional, origens locais controladas.
- O frontend deve receber `VITE_API_URL` apontando para a API Fly do mesmo ambiente.
- Os build args `VITE_PUBLIC_URL` e `VITE_PUBLIC_DUCKDNS_URL` documentam a URL pública primária e o alias DuckDNS para rastreabilidade no artefato publicado.
- Secrets reais devem ser configurados no Fly.io via `fly secrets set`; nunca versionar segredos em arquivos `.toml`, `.env` ou documentação.

## Promoção padrão ouro

1. Publicar e validar `dev`.
2. Promover o mesmo escopo para `staging`.
3. Validar saúde pública, login/autenticação e fluxo afetado em `staging`.
4. Publicar em `prod` somente com CI verde, CORS explícito e secrets produtivos configurados.
5. Registrar evidência do comando `node scripts/validar-acessos-publicos.mjs` após a publicação.

## Comandos de deploy

```powershell
# Backend + frontend do ambiente alvo
.\scripts\fly-deploy.ps1 -Env dev
.\scripts\fly-deploy.ps1 -Env staging
.\scripts\fly-deploy.ps1 -Env prod

# Apenas secrets do backend
.\scripts\fly-deploy.ps1 -Env prod -SecretsOnly
```

## Validação pública

```bash
node scripts/validar-acessos-publicos.mjs
```

A validação cobre os frontends Fly, os aliases DuckDNS e os healthchecks das APIs Fly. Para troubleshooting temporário sem bloquear o terminal local, use:

```bash
ACCESS_VALIDATION_FAIL_ON_UNAVAILABLE=false node scripts/validar-acessos-publicos.mjs
```

## Rollback

- Reimplantar a imagem anterior pelo painel/CLI do Fly.io quando o problema estiver no release recém-publicado.
- Restaurar secrets somente por `fly secrets set`, sem registrar valores no repositório.
- Se o problema for DNS/DuckDNS, manter o domínio Fly como rota canônica de contingência enquanto o alias é corrigido.
