# OCR v2 — Estratégia de Deployment & Transição

**Versão:** 1.0  
**Data:** 2026-09-11  
**Status:** 📋 Ativo  

---

## 🎯 Estratégia: 3 Pilares

```
PILAR 1: GitLab CI (NOW)       PILAR 2: Pausar PC24x7      PILAR 3: Migração Futura
┌──────────────────────┐       ┌──────────────────────┐     ┌──────────────────────┐
│ Deploy em Fly.io     │       │ Não pronto ainda     │     │ Quando PC24x7 pronto │
│ ✅ Ativo             │       │ ⏳ Em preparação     │     │ 📋 Planejado         │
│ • GitLab CI          │       │ • Specs pendentes    │     │ • Fase piloto HML    │
│ • Staging/Prod       │       │ • Docker-compose vazio     │ • Canary prod        │
│ • Fly.io             │       │ • Sem endpoints      │     │ • Cutover completo   │
└──────────────────────┘       └──────────────────────┘     └──────────────────────┘
        2-4 semanas                   N/A                       TBD (> 1 mês)
```

---

## 1️⃣ PILAR 1: Deploy em Fly.io via GitLab CI (NOW)

**Status:** ✅ Implementado  
**Timeline:** 2026-09-11 — ongoing  

### Implementação

**Arquivo:** `gitlab/ci/ocr-deploy-staging.yml`

```yaml
Stages:
  deploy   → Deploy para Fly.io (manual trigger em main)
  validate → Health checks + readiness validation
  evidence → Publicar artefatos
```

**Jobs:**
- `ocr_deploy_staging_fly` — Push para reqsys-api-stg
- `ocr_validate_staging_readiness` — Validar OCR readiness
- `ocr_validate_staging_health` — Health endpoints
- `ocr_integration_tests_staging` — Testes OCR
- `ocr_publish_staging_evidence` — Consolidar evidência
- `ocr_notify_slack_*` — Notificações

### Como Usar

```bash
# 1. Garantir que FLY_API_TOKEN está em GitLab Settings > CI/CD > Variables
# 2. Merge PR para main
# 3. Ir para GitLab > CI/CD > Pipelines > Seu pipeline
# 4. Clicar em "Play" no job ocr_deploy_staging_fly
# 5. Aguardar ~5 minutos para conclusão
# 6. Validações rodam automaticamente
# 7. Slack notification enviada
```

### Validações

✅ Health check: `/health` → 200  
✅ OCR readiness: `/v1/ocr/readiness` → ready=true  
✅ Métricas: `/metrics` → ocr_* disponíveis  
✅ Testes: Integration tests passam  
✅ Evidência: `audit/ocr/staging-deploy-evidence.json`  

### Monitoramento Pós-Deploy

```
URL: https://reqsys-api-stg.fly.dev
Health: https://reqsys-api-stg.fly.dev/health
Readiness: https://reqsys-api-stg.fly.dev/v1/ocr/readiness
Metrics: https://reqsys-api-stg.fly.dev/metrics
```

---

## 2️⃣ PILAR 2: Pause PC24x7 (Hold Pattern)

**Status:** ⏳ Aguardando  
**Timeline:** Indefinido até PC24x7 estar pronto  

### Situação Atual

```
PC24x7 Infrastructure Status:
├── docker-compose.hml.yml     ❌ VAZIO
├── docker-compose.prod.yml    ❌ VAZIO
├── Networking/LB              ❌ Não configurado
├── Persistent storage         ❌ Não definido
├── Secrets management         ❌ Não definido
├── Endpoints (staging)        ❌ Não definido
└── Endpoints (prod)           ❌ Não definido
```

### Checklist de Desbloqueiadores

Para sair de "hold pattern" e começar Fase 1:

- [ ] DevOps: `docker-compose.hml.yml` preenchido
- [ ] DevOps: `docker-compose.prod.yml` preenchido
- [ ] DevOps: Networking/load-balancer operacional
- [ ] DevOps: Persistent volumes configurados
- [ ] Security: Vault/secrets management integrado
- [ ] Ops: Endpoints validados (staging + prod)
- [ ] Ops: Health check endpoints funcionando
- [ ] Ops: Monitoring/alerting configurado

### O que NÃO fazer

❌ Não force PC24x7 antes de estar pronto  
❌ Não migre sem docker-compose completo  
❌ Não mantenha Fly.io + PC24x7 simultaneamente (caro)  
❌ Não desative Fly.io antes de PC24x7 estar stable

---

## 3️⃣ PILAR 3: Migração para PC24x7 (Future)

**Status:** 📋 Planejado  
**Timeline:** Após PC24x7 pronto (> 1 mês)  
**Document:** `docs/architecture/ocr-pc24x7-migration-plan.md`

### 3 Fases de Migração

```
Fase 0: Preparação
├─ PC24x7 HML/PROD docker-compose
├─ Networking validado
├─ Secrets configurados
└─ Endpoints testados

Fase 1: Staging Piloto (HML)
├─ Deploy OCR em PC24x7 HML
├─ Validação 1-2 semanas
├─ Rollback para Fly.io se falhar
└─ ✅ Sucesso → Fase 2

Fase 2: Production Canary (PROD)
├─ Canary: 5% → 25% → 100%
├─ Monitoramento intensivo
├─ Rollback automático se error > 1%
└─ ✅ Estável 2-4 semanas → Fase 3

Fase 3: Cutover Completo
├─ Zero traffic em Fly.io
├─ Desligar reqsys-api-stg + reqsys-api
├─ Arquivar configs
└─ ✅ Completo → PC24x7 único
```

### Timeline Estimada

```
2026-09-11: GitLab CI + Fly.io ✅ Pronto
2026-09-??:  PC24x7 specs vindo → Fase 0 começa
2026-10-??: PC24x7 HML pronto → Fase 1 começa
2026-10-??: PC24x7 PROD canary → Fase 2 começa
2026-11-??: PC24x7 stable → Fase 3 begins
2026-11-??: Fly.io desligado → Cutover completo
```

---

## 📊 Estado por Semana

### Semana 1-2 (Agora)
```
Staging:    ✅ Fly.io (via GitLab CI)
Production: ✅ Fly.io (manual)
PC24x7:     ❌ Blocked (specs)
Deploy:     📋 GitLab CI ready
```

### Semana 3-4 (PC24x7 começando)
```
Staging:    ✅ Fly.io (active)
Production: ✅ Fly.io (active)
PC24x7:     ⏳ Fase 0 (build docker-compose)
Deploy:     ✅ Ambos ready (dual-track)
```

### Semana 5-6 (PC24x7 HML)
```
Staging:    ✅ Fly.io + PC24x7 HML (validation)
Production: ✅ Fly.io (stable)
PC24x7:     ⏳ Fase 1 (1-2 week soak)
Deploy:     ✅ Both platforms
```

### Semana 7-10 (PC24x7 PROD)
```
Staging:    ✅ PC24x7 HML (if stable) | Fly.io backup
Production: ⏳ PC24x7 PROD (canary 5%→25%→100%)
PC24x7:     ⏳ Fase 2 (2-4 week soak)
Deploy:     ✅ Dual (migration in progress)
```

### Semana 11+ (Cutover)
```
Staging:    ✅ PC24x7 HML
Production: ✅ PC24x7 PROD
PC24x7:     ✅ Fase 3 (cutover complete)
Deploy:     ✅ PC24x7 only
Fly.io:     ❌ Desligado (cost savings)
```

---

## 🎯 Decisões & Riscos

### Decisão 1: Não esperar PC24x7

**Por que:** PC24x7 não está pronto hoje. OCR precisa estar em staging NOW.

**Ação:** Deploy em Fly.io via GitLab CI.

**Risco:** Manter dois ambientes (custo + complexidade).

**Mitigação:** Plano de migração claro para PC24x7.

---

### Decisão 2: Pausar PC24x7 até estar pronto

**Por que:** Docker-compose vazio = não é deployable.

**Ação:** Hold pattern até DevOps completar specs.

**Risco:** Atraso na migração se PC24x7 tomar mais tempo.

**Mitigação:** Monitoramento semanal com DevOps.

---

### Decisão 3: Canary approach para migração

**Por que:** Production é crítico.

**Ação:** Fase 1 (HML) → Fase 2 (canary) → Fase 3 (cutover).

**Risco:** Timeline longa (8+ semanas).

**Mitigação:** Parallel-track permite rollback rápido.

---

## 📋 Checklist de Implementação

### Hoje (2026-09-11)

- [x] Criar `gitlab/ci/ocr-deploy-staging.yml`
- [x] Criar `docs/architecture/ocr-pc24x7-migration-plan.md`
- [x] Criar `docs/architecture/ocr-deployment-strategy.md` (este arquivo)
- [ ] Testar GitLab CI job (manual trigger)
- [ ] Validar Slack notifications
- [ ] Comunicar timeline ao time

### Semana Próxima

- [ ] Sincronizar com DevOps sobre PC24x7 timeline
- [ ] Obter docker-compose template
- [ ] Preparar specs de secrets vault
- [ ] Documentar rollback procedures

### Quando PC24x7 specs chegam

- [ ] Preencher docker-compose.hml.yml
- [ ] Testar build + push de imagens
- [ ] Validação de networking
- [ ] Executar Fase 1 piloto

---

## 📞 Contatos & Escalação

| Papel | Contato | Para |
|-------|---------|------|
| **Team OCR** | @ericson-j-santos | Deploy, testes, validação |
| **DevOps** | @devops-team | PC24x7 specs, docker-compose |
| **Security** | @security-team | Vault, secrets management |
| **Ops** | @ops-team | Monitoring, alerting |

---

## 📚 Documentação Relacionada

1. **Deploy (Fly.io):**
   - `docs/runbooks/ocr-deploy-staging.md` — Manual deploy
   - `gitlab/ci/ocr-deploy-staging.yml` — GitLab CI job

2. **Migração (PC24x7):**
   - `docs/architecture/ocr-pc24x7-migration-plan.md` — Plano detalhado
   - (docker-compose templates — TBD)

3. **Arquitetura (OCR):**
   - `docs/architecture/ocr-secure-review-v2.md` — Spec técnico
   - `docs/guides/ocr-setup-local-development.md` — Local setup

---

**Status:** ✅ Strategy defined, ready to execute  
**Próxima revisão:** 2026-09-25  
**Responsável:** Team OCR
