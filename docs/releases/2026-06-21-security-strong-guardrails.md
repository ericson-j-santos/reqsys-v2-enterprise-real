# Release Note — Security Strong Guardrails

- **Data:** 2026-06-21
- **PR:** #70
- **Branch:** `ci/enterprise-continuous-maturity`
- **Tipo:** Segurança / Governança / CI
- **Ambiente:** Documentação, governança e CI sem alteração direta de runtime

## Resumo

Adicionada camada forte de guardrails de segurança para bloquear configurações inseguras antes de merge/deploy.

## Arquivos adicionados

| Arquivo | Objetivo |
|---|---|
| `.github/workflows/security-strong-guardrails.yml` | Workflow bloqueante de segurança |
| `scripts/security_strong_guardrails.py` | Scanner determinístico de configurações críticas |
| `docs/adr/ADR-2026-06-21-security-strong-guardrails.md` | Decisão arquitetural |
| `docs/governanca/SECURITY_STRONG_GUARDRAILS.md` | Runbook operacional |
| `docs/releases/2026-06-21-security-strong-guardrails.md` | Release note |

## Gates implementados

| Categoria | Gate | Resultado esperado |
|---|---|---|
| Auth | Auth desligada | Falha CI |
| Auth | Login demo habilitado | Falha CI |
| CORS | Wildcard | Falha CI |
| JWT | Validação desligada | Falha CI |
| TLS | Validação desligada | Falha CI |
| Logging | Dump de ambiente | Falha CI |
| Supply chain | Actions por tag | Alerta |
| Permissões | Permissões write amplas | Alerta |

## Validação esperada

- Workflow `Security Strong Guardrails` executado no PR.
- Artefato `security-strong-guardrails` publicado.
- PR mantido em draft até CI verde.

## Risco conhecido

O scanner pode revelar débitos existentes. Isso deve ser tratado como evidência real e não como motivo para rebaixar o gate.
