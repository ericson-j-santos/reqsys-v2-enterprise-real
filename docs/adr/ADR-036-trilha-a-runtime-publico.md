# ADR-036 — Trilha A: Runtime Público

## Status

Aceito em 2026-06-27.

## Contexto

O runtime público Fly.io precisava de validação versionada, boot resiliente com volume `/data`, healthcheck em camadas e validador consolidado com fallback de evidência — evoluindo de forma isolada das demais trilhas.

## Decisão

Formalizar a **Trilha A — Runtime Público** com pacote de governança padrão ouro:

| Componente | Artefato canônico |
|---|---|
| Boot resiliente | `scripts/fly_boot.sh` |
| Healthcheck | `Dockerfile.fly`, `fly.toml`, `backend/app/core/runtime_boot.py` |
| Validador consolidado | `scripts/runtime_public_validator.py` |
| Wrapper padrão ouro | `scripts/trilha_a_runtime_publico.py` |
| Runbook | `docs/runbooks/trilha-a-runtime-publico.md` |
| Architecture-as-code | `docs/architecture/trilha-a/architecture-as-code.json` |

Validação report-only via workflow `trilha-a-runtime-publico.yml`.

## Regras de governança

| Tema | Decisão |
|---|---|
| Modo | `report_only` — não substitui CI principal nem executa deploy automático |
| Secrets | Não criar secrets Fly nem GitHub no validador |
| Fallback | Cache de evidência apenas para diagnóstico; probe live é preferencial |
| Produção | `REQSYS_BOOT_FALLBACK=false` obrigatório em produção |

## Consequências

### Benefícios

- Runtime público auditável e versionado junto ao código.
- Boot resiliente documentado e validável localmente.
- Fallback progressivo reduz falsos negativos em CI sem rede.

### Limitações

- Probe live depende de URL pública disponível.
- Docker smoke pode ser pulado em ambientes sem daemon.

## Rollback

Reverter `docs/architecture/trilha-a/`, ADR-036, workflow e wrapper; manter `runtime_public_validator.py` se ainda necessário para fly-runtime-p0.

## Referências

- `docs/runbooks/trilha-a-runtime-publico.md`
- `docs/agents/runtime-public/README.md`
- `docs/architecture/trilhas/trilhas-registry.json`
