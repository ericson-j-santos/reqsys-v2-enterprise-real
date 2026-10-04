---
status: ReqSys / Plataforma Corporativa
date: 2026-06-22
deciders: Arquitetura / Engenharia
context: ReqSys / Plataforma Corporativa
version: 1.0.0
---

# ADR-023 — NGINX Secure Profile para ReqSys


## Status

Proposto para validação em PR.

## Contexto

O ReqSys possui gates de segurança para produção, autenticação, CORS, JWT, auditoria e operação governada. Faltava um baseline versionado e validável para reverse proxy NGINX.

## Decisão

Adicionar um perfil seguro de NGINX em `infra/nginx`, com validação estática por `tools/validate_nginx_security.py` e workflow dedicado `NGINX Security Profile`.

## Controles obrigatórios

- Redirecionamento HTTP para HTTPS.
- TLS mínimo 1.2/1.3.
- `server_tokens off`.
- Security headers: HSTS, CSP, X-Frame-Options, nosniff, Referrer-Policy e Permissions-Policy.
- CORS por allowlist, sem wildcard.
- Rate limit e connection limit.
- Propagação de `X-Request-ID` e `X-Correlation-ID`.
- Bloqueio de rotas sensíveis em produção.
- Logs JSON com request id.

## Consequências

- O baseline passa a ser auditável e versionado.
- Mudanças inseguras passam a ser bloqueadas no CI.
- A implantação real ainda exige ajuste dos hosts, certificados e upstreams por ambiente.
