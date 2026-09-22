# OCR v2 — Próximas Ações (Action Items)

**Versão:** 1.0  
**Data:** 2026-09-11  
**Status:** ✅ Ready to execute  
**Owner:** Team OCR  

---

## 📋 Sumário Executivo

3 itens implementados em paralelo:

| # | Item | Status | Timeline | Owner |
|----|------|--------|----------|-------|
| **1** | ✅ Update GitLab CI deploy workflow | ✅ Done | 2026-09-11 | Team OCR |
| **2** | ⏳ Hold PC24x7 deployment | ⏳ Waiting | TBD | DevOps |
| **3** | 📋 Prepare migration plan | ✅ Done | 2026-09-11 | Team OCR |

---

## 🎯 ITEM 1: Update GitLab CI Deploy Workflow

**Status:** ✅ **IMPLEMENTADO**

### O que foi feito

✅ Criar `gitlab/ci/ocr-deploy-staging.yml`
- Deploy para Fly.io staging (reqsys-api-stg)
- Validações pós-deploy (readiness, health, integration tests)
- Publicação de evidência em `audit/ocr/`
- Notificações Slack (sucesso + falha)

✅ Integrar ao `.gitlab-ci.yml` principal
- Adicionado include: `- local: gitlab/ci/ocr-deploy-staging.yml`

### Como usar

```bash
# 1. Merge PR para main
git push origin fix/ocr-deploy-gitlab-ci:main

# 2. Ir para GitLab UI
# GitLab > CI/CD > Pipelines > Seu pipeline

# 3. Clicar em "Play" no job:
ocr_deploy_staging_fly

# 4. Aguardar ~5 minutos
# - Deploy (Fly.io)
# - Validações (readiness, health, tests)
# - Evidência (audit/ocr/)
# - Slack notification

# 5. Verificar resultado
https://reqsys-api-stg.fly.dev/v1/ocr/readiness
```

### Pré-requisitos

❌ **PENDENTE:** Configurar variáveis de CI em GitLab:

```
Settings > CI/CD > Variables
  - FLY_API_TOKEN  (Fly.io auth token)
  - OCR_DATA_ENCRYPTION_KEY  (32 bytes Base64)
  - SLACK_WEBHOOK_OCR  (Slack incoming webhook)
```

**Gerar FLY_API_TOKEN:**
```bash
# Já existente no Fly.io account
# Copiar de: fly.io/account/access-tokens
```

**Gerar OCR_DATA_ENCRYPTION_KEY:**
```bash
python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
# Copiar output para GitLab Variables
```

**Gerar SLACK_WEBHOOK_OCR:**
```bash
# Slack > Settings > Apps > Incoming Webhooks
# Criar novo webhook
# Copiar URL
```

### Arquivos Envolvidos

- ✅ `gitlab/ci/ocr-deploy-staging.yml` — Deploy job
- ✅ `.gitlab-ci.yml` — Include adicionado
- ✅ `docs/architecture/ocr-deployment-strategy.md` — Documentação

### Checklist de Ativação

```
[ ] Criar FLY_API_TOKEN em GitLab Variables
[ ] Criar OCR_DATA_ENCRYPTION_KEY em GitLab Variables
[ ] Criar SLACK_WEBHOOK_OCR em GitLab Variables
[ ] Merge PR para main
[ ] Testar job ocr_deploy_staging_fly (play button)
[ ] Validar Fly.io deployment (reqsys-api-stg)
[ ] Validar Slack notification
[ ] Revisar audit/ocr/staging-deploy-evidence.json
```

---

## 🎯 ITEM 2: Pausar PC24x7 Deployment

**Status:** ⏳ **AGUARDANDO DEVOPS**

### O que precisa ser feito

❌ PC24x7 não está pronto. Checklist de desbloqueiadores:

```
[ ] DevOps: docker-compose.hml.yml preenchido
[ ] DevOps: docker-compose.prod.yml preenchido
[ ] DevOps: Networking/load-balancer operacional
[ ] DevOps: Persistent volumes configurados
[ ] Security: Vault/secrets management integrado
[ ] Ops: Endpoints definidos (staging + prod URLs)
[ ] Ops: Health check endpoints funcionando
[ ] Ops: Monitoring/alerting configurado
```

### Estado Atual

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

### Timeline

- **Semana 1-2:** Aguardar specs de PC24x7
- **Semana 3-4:** DevOps começa Fase 0 (preparação)
- **Semana 5-6:** HML pronto para Fase 1 (piloto)
- **Semana 7+:** PROD canary (Fase 2)

### Ação Imediata

📧 **Enviar email para DevOps:**

```
Subject: Desbloquear PC24x7 para OCR v2 — Specs Needed

Olá DevOps Team,

Estamos prontos para migrar OCR v2 de Fly.io para PC24x7 quando a infra estiver pronta.

Checklist de desbloqueiadores (vide docs/architecture/ocr-pc24x7-migration-plan.md):

[ ] docker-compose.hml.yml preenchido (com OCR backend + worker)
[ ] docker-compose.prod.yml preenchido (HA setup com 3 replicas)
[ ] Networking/load-balancer operacional
[ ] Persistent volumes para OCR_INPUT_ROOT
[ ] Vault/secrets management integrado
[ ] Endpoints definidos (staging + prod URLs)
[ ] Health check endpoints funcionando
[ ] Monitoring/alerting configurado

Podemos fazer uma call para alinhamento? Timeline estimada?

Documento detalhado: docs/architecture/ocr-pc24x7-migration-plan.md

Obrigado!
```

---

## 🎯 ITEM 3: Preparar Plano de Migração

**Status:** ✅ **IMPLEMENTADO**

### O que foi criado

✅ `docs/architecture/ocr-pc24x7-migration-plan.md`
- 3 fases de migração (Prep, Staging Piloto, PROD Canary, Cutover)
- Docker-compose template para HML/PROD
- Critérios de sucesso por fase
- Rollback strategies
- Timeline estimada

✅ `docs/architecture/ocr-deployment-strategy.md`
- 3 pilares consolidados
- Decisões + riscos
- Estado por semana
- Contatos & escalação

### Como usar quando PC24x7 tiver specs

```bash
# 1. Quando DevOps fornecer docker-compose
# - Preencher docker-compose.hml.yml (usando template)
# - Preencher docker-compose.prod.yml
# - Testar build + push de imagens

# 2. Seguir Fase 0 em ocr-pc24x7-migration-plan.md
# - Validar networking
# - Configurar secrets vault
# - Testar endpoints

# 3. Executar Fase 1 (HML)
# - Deploy em PC24x7 HML
# - Validar readiness por 1-2 semanas
# - Ir para Fase 2 se tudo ok

# 4. Executar Fase 2 (PROD Canary)
# - Canary: 5% → 25% → 100%
# - Monitorar por 2-4 semanas
# - Ir para Fase 3 se stable

# 5. Executar Fase 3 (Cutover)
# - Zero traffic em Fly.io
# - Desligar reqsys-api-stg + reqsys-api
# - Arquivar configs
```

### Arquivos Criados

- ✅ `docs/architecture/ocr-pc24x7-migration-plan.md` — Plano detalhado
- ✅ `docs/architecture/ocr-deployment-strategy.md` — Estratégia consolidada
- ✅ `docs/runbooks/ocr-deployment-action-items.md` — Este arquivo

---

## 🚀 Resumo: O que fazer AGORA

### Hoje (2026-09-11)

```bash
# 1. Fazer merge do PR com:
#    - gitlab/ci/ocr-deploy-staging.yml
#    - .gitlab-ci.yml (include adicionado)
#    - docs/architecture/ocr-*.md

git push origin <seu-branch>:main

# 2. Criar PR no GitHub
# - Title: "OCR v2: Deploy para GitLab CI + Plano de migração para PC24x7"
# - Reference: docs/architecture/ocr-deployment-strategy.md
```

### Próxima semana

```bash
# 3. Configurar GitLab CI Variables
Settings > CI/CD > Variables
  - FLY_API_TOKEN
  - OCR_DATA_ENCRYPTION_KEY
  - SLACK_WEBHOOK_OCR

# 4. Testar deploy
GitLab > CI/CD > Pipelines > Play ocr_deploy_staging_fly

# 5. Enviar email para DevOps (item 2 acima)
```

### Quando PC24x7 tiver specs

```bash
# 6. Começar Fase 0 (ocr-pc24x7-migration-plan.md)
# 7. Preencher docker-compose files
# 8. Executar Fase 1 (HML piloto)
```

---

## 📞 Contatos

| Papel | Contato | Para |
|-------|---------|------|
| **Team OCR** | @ericson-j-santos | Deploy, testes, validação |
| **DevOps** | @devops-team | PC24x7 specs, docker-compose |
| **Security** | @security-team | Vault, secrets management |
| **Ops** | @ops-team | Monitoring, alerting |

---

## 📚 Documentação

1. **Deploy (Fly.io):**
   - `docs/runbooks/ocr-deploy-staging.md` — Manual deploy
   - `gitlab/ci/ocr-deploy-staging.yml` — GitLab CI job
   - `docs/runbooks/ocr-deployment-action-items.md` — Este arquivo

2. **Migração (PC24x7):**
   - `docs/architecture/ocr-pc24x7-migration-plan.md` — Plano detalhado
   - `docs/architecture/ocr-deployment-strategy.md` — Estratégia consolidada

3. **Arquitetura (OCR):**
   - `docs/architecture/ocr-secure-review-v2.md` — Spec técnico
   - `docs/guides/ocr-setup-local-development.md` — Local setup

---

## ✅ Checklist Final

```
Item 1: GitLab CI Deploy (IMPLEMENTADO)
  [x] Criar gitlab/ci/ocr-deploy-staging.yml
  [x] Integrar ao .gitlab-ci.yml
  [ ] Configurar variáveis GitLab (pending)
  [ ] Testar job (pending)

Item 2: PC24x7 Hold (AGUARDANDO DEVOPS)
  [ ] Enviar checklist para DevOps
  [ ] Obter specs de docker-compose
  [ ] Validar endpoints
  [ ] Começar Fase 0

Item 3: Migração Plan (IMPLEMENTADO)
  [x] Criar ocr-pc24x7-migration-plan.md
  [x] Criar ocr-deployment-strategy.md
  [x] Documentar 3 fases
  [x] Criar rollback strategies
```

---

**Status:** ✅ Ready to execute  
**Próxima ação:** Configure GitLab CI Variables + Test deploy  
**Responsável:** Team OCR
