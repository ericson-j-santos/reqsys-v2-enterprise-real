# Runbook — NGINX Secure Profile

## Objetivo

Operar o ReqSys atras de um reverse proxy NGINX com baseline seguro, auditavel e validado por CI.

## Arquivos principais

| Arquivo | Finalidade |
|---|---|
| `infra/nginx/nginx.conf` | Configuracao principal do proxy |
| `infra/nginx/conf.d/security-headers.conf` | Headers de seguranca |
| `infra/nginx/conf.d/cors.conf` | CORS por allowlist |
| `infra/nginx/conf.d/tls.conf` | TLS minimo e sessoes |
| `infra/nginx/conf.d/rate-limit.conf` | Rate limit e connection limit |
| `tools/validate_nginx_security.py` | Gate estatico |

## Validacao local

```bash
python tools/validate_nginx_security.py
```

## Validacao com NGINX

```bash
docker run --rm \
  -v "$PWD/infra/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
  -v "$PWD/infra/nginx/conf.d:/etc/nginx/conf.d:ro" \
  nginx:1.27-alpine nginx -t
```

## Checklist antes de producao

- Ajustar `server_name` para o dominio real.
- Montar certificados por secret/volume seguro.
- Revisar allowlist de CORS por ambiente.
- Validar upstreams reais.
- Executar teste dinamico de headers.
- Executar scan TLS externo.
- Validar logs com `request_id` e sem PII.

## Criterio de pronto

- Workflow `NGINX Security Profile` verde.
- CI sem regressao.
- ADR e runbook versionados.
- Evidencia no GitHub Actions.
