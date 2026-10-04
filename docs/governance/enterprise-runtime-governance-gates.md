# Enterprise Runtime Governance Gates

## Objetivo

Adicionar uma camada preventiva de governança enterprise para bloquear padrões incompatíveis com produção segura, auditável e rastreável.

## Gates implementados

| Código | Severidade | Validação |
|---|---:|---|
| `SEC_SECRET_HARDCODED` | Alta | Segredos, tokens ou senhas hardcoded |
| `SEC_CORS_WILDCARD` | Alta | CORS wildcard |
| `SEC_TLS_VERIFY_FALSE` | Alta | TLS verification desabilitada |
| `SEC_HTTP_INSECURE` | Média | HTTP inseguro fora de localhost |
| `LGPD_PII_LOGGING` | Alta | Logs contendo PII ou segredos |
| `SEC_CONNECTION_STRING` | Alta | Connection strings expostas |
| `OBS_CORRELATION_ID_MISSING` | Média | Ausência de `correlation_id` no código operacional |

## Arquivos adicionados

- `.github/workflows/enterprise-runtime-governance-gates.yml`
- `scripts/governance/enterprise_runtime_governance_gates.py`

## Critérios de aceite

- Workflow `Enterprise Runtime Governance Gates` verde.
- `Governance Quality Gates` verde.
- `CI Enterprise Fast` verde.
- `Branch Protection Audit` verde.
- PR pequeno, sem alteração funcional de runtime.

## Decisão operacional

Este gate é preventivo e deve evoluir incrementalmente para incluir:

- actionlint;
- shellcheck;
- markdownlint;
- validação de ADR;
- validação de changelog;
- SBOM;
- CodeQL obrigatório;
- SARIF artifact.
