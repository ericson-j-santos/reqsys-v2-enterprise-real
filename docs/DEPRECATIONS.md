# Deprecations — Remoções e Migrações

Este documento lista componentes, scripts e configurações removidos do repositório, com o motivo e o caminho de migração.

---

## Fly.io — Descontinuado (2026-09-11)

**Motivo:** Migração completa para PC 24x7 reduz custo operacional em ~90% (R$300/mês → R$30/mês).

**Timeline:**
- **2026-09-09** — ADR-046 proposto (piloto dev)
- **2026-09-11** — Decisão: migração COMPLETA (dev + hml + prod)
- **2026-09-11** — Implementação completa (80 arquivos Fly removidos)
- **2026-09-11** — Infraestrutura PC24x7 criada (repo separado)

**Caminho de Migração:** Ver [ADR-046](docs/ADR/ADR-046-pc24x7-substituicao-flyio.md) e [Infrastructure Repo](https://github.com/ericson-j-santos/reqsys-infrastructure-pc24x7)

---

## Arquivos Removidos

### Configuração Fly (13 arquivos)

```
fly.toml                              — Config raiz Fly.io
backend/fly.toml                      — Config API prod
backend/fly.dev.toml                  — Config API dev
backend/fly.staging.toml              — Config API hml
frontend/fly.toml                     — Config Frontend prod
frontend/fly.dev.toml                 — Config Frontend dev
frontend/fly.staging.toml             — Config Frontend hml
infra/dev/fly.toml                    — Config dev override
infra/hml/fly.toml                    — Config hml override
infra/prod/fly.toml                   — Config prod override
services/environment-observability-api/fly.*.toml  — Config 3 envs
```

**Substituído por:** `docker-compose.yml` (base) + `docker-compose.{dev,hml,prod}.yml` (overrides)

---

### Dockerfiles Fly (2 arquivos)

```
Dockerfile.fly              — Dockerfile específico Fly (raiz)
backend/Dockerfile.fly      — Dockerfile específico Fly (backend)
```

**Substituído por:** `backend/Dockerfile` (genérico, funciona em qualquer plataforma)

---

### Scripts Fly (8 arquivos)

```
scripts/fly-deploy.ps1                    — Deploy PowerShell via flyctl
scripts/fly_boot.sh                       — Boot script Fly
scripts/capture_fly_environment_state.py  — Captura estado Fly (for audit)
scripts/check_fly_secret_strength.py      — Valida secrets Fly
scripts/configurar_fly_auth_azure.py      — Auth Azure/Fly integration
scripts/validate_fly_enterprise_sync.py   — Valida sync Fly enterprise
scripts/validate_fly_runtime_config.py    — Valida config runtime Fly
.tmp/flyctl/install.ps1                   — Instalação flyctl
```

**Substituído por:** 
- Deploy: `.github/workflows/deploy-pc24x7-{dev,hml,prod}.yml` (em infrastructure repo)
- Health/validation: `scripts/pc24x7_backup_restic.sh` + systemd units

---

### Testes Fly (25+ arquivos)

Todos os testes que validavam infraestrutura Fly.io foram removidos:

```
tests/test_fly_automatic_promotion_*.py (15+ arquivos)
  - test_fly_automatic_promotion_adr.py
  - test_fly_automatic_promotion_all_files.py
  - test_fly_automatic_promotion_architecture.py
  - test_fly_automatic_promotion_contract.py
  - test_fly_automatic_promotion_docs.py
  - test_fly_automatic_promotion_dod.py
  - test_fly_automatic_promotion_evidence_map.py
  - test_fly_automatic_promotion_guardrails.py
  - test_fly_automatic_promotion_index.py
  - test_fly_automatic_promotion_kpis.py
  - test_fly_automatic_promotion_local_validation.py
  - test_fly_automatic_promotion_runbook.py
  - test_fly_automatic_promotion_schema.py
  - test_fly_automatic_promotion_security_contract.py

tests/test_capture_fly_environment_state.py
tests/test_configurar_fly_auth_azure.py
tests/test_configurar_fly_auth_bacen_gate_contract.py
tests/test_fly_command_center_bacen_gate_contract.py
tests/test_fly_copilot_memory_runtime_contract.py
tests/test_fly_dev_fast_deploy_contract.py
tests/test_fly_dev_runtime_diagnostic_contract.py
tests/test_fly_dockerfile_local_modules_contract.py
tests/test_fly_enterprise_sync_*.py (5+ arquivos)
tests/test_fly_environment_homologation_bacen_gate_contract.py
tests/test_fly_environment_state_capture_schema.py
tests/test_fly_runtime_p0_bacen_gate_contract.py
tests/test_governed_post_merge_fly_sync_workflow.py
```

**Substituído por:** Testes de health check em PC24x7 (via systemd + docker-compose)

---

### CI/CD Workflows Fly (10 arquivos)

```
.github/workflows/fly-automatic-environment-promotion.yml
.github/workflows/fly-dev-fast-deploy.yml
.github/workflows/fly-dev-runtime-diagnostic.yml
.github/workflows/fly-enterprise-sync.yml
.github/workflows/fly-environment-evidence-capture.yml
.github/workflows/fly-environment-homologation-gate.yml
.github/workflows/fly-environment-promotion-stage.yml
.github/workflows/fly-governed-command-center.yml
.github/workflows/fly-org-token-successor-probe.yml
.github/workflows/fly-runtime-p0.yml
```

**Substituído por:** `.github/workflows/deploy-pc24x7-{dev,hml,prod}.yml` (em infrastructure repo)

---

### Documentação Fly (30+ arquivos)

```
docs/ADR/ADR-automatic-fly-environment-promotion.md
docs/changelog/fly-*.md (3 arquivos)
docs/checklists/fly-*.md
docs/contracts/fly-*.md (2 arquivos + schema.json)
docs/decisions/ADR-automatic-fly-environment-promotion.md
docs/governance/fly-*.md
docs/metrics/fly-*.md
docs/operations/fly-*.md
docs/operacao/fly-*.md
docs/runbooks/fly-*.md (5+ arquivos)
docs/runbooks/producao-flyio-*.md
docs/runbooks/migracao-postgres-fly.md
docs/security/fly-*.md
docs/evidencias-operacionais/templates/flyio-*.json
artifacts/fly-*.json (2+ arquivos)
```

**Substituído por:**
- [ADR-046 — PC próprio 24x7](docs/ADR/ADR-046-pc24x7-substituicao-flyio.md) — Decisão arquitetural
- [Infrastructure Repo Docs](https://github.com/ericson-j-santos/reqsys-infrastructure-pc24x7) — Runbook completo

---

## Secrets & Variáveis GitHub Removidos

### Secrets (remover manualmente via GitHub UI)

```
FLY_API_TOKEN          — Token API Fly.io
FLY_ORG                — Organização Fly.io
```

### Variáveis de Ambiente (remover manualmente via GitHub UI)

```
FLY_APP_DEV            — App Fly dev (reqsys-api-dev, reqsys-app-dev)
FLY_APP_HML            — App Fly hml (reqsys-api-stg, reqsys-app-stg)
FLY_APP_PROD           — App Fly prod (reqsys-api, reqsys-app)
```

**Substituído por:** `PC24X7_*` secrets (já adicionados em PR #1603)

---

## O Que Fazer Agora

### Para Usar ReqSys em PC24x7

1. **Clone o repositório infrastructure:**
   ```bash
   git clone https://github.com/ericson-j-santos/reqsys-infrastructure-pc24x7.git
   cd reqsys-infrastructure-pc24x7
   ```

2. **Siga o runbook:**
   - [docs/setup-linux.md](https://github.com/ericson-j-santos/reqsys-infrastructure-pc24x7/blob/main/docs/setup-linux.md) — Linux
   - [docs/setup-wsl2.md](https://github.com/ericson-j-santos/reqsys-infrastructure-pc24x7/blob/main/docs/setup-wsl2.md) — WSL2 + Ubuntu

3. **Deploy:**
   ```bash
   cd /home/reqsys-admin/reqsys-dev
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
   ```

4. **Backup:**
   ```bash
   ./scripts/pc24x7_backup_restic.sh dev
   ```

5. **Systemd (autostart):**
   ```bash
   sudo systemctl enable reqsys-dev.service
   sudo systemctl start reqsys-dev.service
   ```

---

## Para Manter Fly.io (Não Recomendado)

Se, por algum motivo, precisar manter Fly.io:

1. **Reverter commit de limpeza** (não recomendado)
2. **Usar arquivo histórico** — checkout de antes de 2026-09-11
3. **Entre em contato** — discuss com a equipe

---

## Referências

- [ADR-046 — PC próprio 24x7 como substituto do Fly.io](docs/ADR/ADR-046-pc24x7-substituicao-flyio.md)
- [Infrastructure Repository](https://github.com/ericson-j-santos/reqsys-infrastructure-pc24x7)
- [PR #1603 — Migração PC24x7](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/1603)

---

## Histórico de Remoção

| Data | Fases Removidas | Arquivos |
|------|-----------------|----------|
| 2026-09-11 | 1-5 (todas) | 80 |
| 2026-09-11 | Deprecation doc | Este arquivo |

**Removido por:** Claude Haiku 4.5  
**Autorizado por:** Usuário (decision: migração completa PC24x7)
