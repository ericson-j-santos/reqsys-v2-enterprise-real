# Release Note — NGINX Secure Profile v1.0.0

## Entregas

- Baseline seguro de NGINX em `infra/nginx`.
- CORS governado por allowlist.
- TLS minimo 1.2/1.3.
- Security headers obrigatorios.
- Rate limit e connection limit.
- Bloqueio de rotas sensiveis.
- Propagacao de `X-Request-ID` e `X-Correlation-ID`.
- Validador estatico versionado.
- Workflow de gate dedicado.
- ADR e runbook operacional.

## Validacao

```bash
python tools/validate_nginx_security.py
```

## Pendencias para producao

- Substituir `reqsys.example.com` pelo dominio real.
- Montar certificado real por secret.
- Confirmar upstreams reais por ambiente.
- Executar scan TLS e headers em endpoint publicado.
