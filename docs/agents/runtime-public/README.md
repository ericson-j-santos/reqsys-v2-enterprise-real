# REQSYS#002 — IA Runtime Público / Deploy Runtime

## Identidade operacional

- Frente: `REQSYS#002`
- Agente: `IA_RUNTIME_PUBLICO`
- Trilha paralela: **A — Runtime Público**
- Branch padrão: `cursor/trilha-a-runtime-publico-6e8a`
- Ambiente alvo: `dev → staging → produção`

## Objetivo

Estabilizar a publicação pública e a operação runtime do ReqSys com deploy governado, health checks, boot resiliente, fallback de evidência e validador consolidado.

## Escopo autorizado (Trilha A)

- `fly.toml`, `Dockerfile.fly`, `scripts/fly_boot.sh`
- Healthcheck Fly + Docker + `/health` com probe de banco
- `scripts/runtime_public_validator.py`
- Workflow `ReqSys Fly Runtime P0`
- Runbook `docs/runbooks/trilha-a-runtime-publico.md`

## Fora de escopo

- Alterar secrets diretamente
- Relaxar gates de produção
- Deploy automático em schedule
- Alterar workflows de governança sem REQSYS#005

## Definition of Done

1. PR com escopo pequeno e rastreável
2. CI `fly-runtime-p0` verde em PR
3. Validador consolidado publica artifact
4. Boot resiliente documentado e testado
5. Sem relaxamento de segurança

## Estado atual

- Trilha A implementada no repositório com validador consolidado e boot resiliente
- Deploy Fly real continua manual via `workflow_dispatch deploy=true`
- Evidência pública em `audit/runtime/` alimenta fallback do validador

## Runbook

[`docs/runbooks/trilha-a-runtime-publico.md`](../runbooks/trilha-a-runtime-publico.md)
