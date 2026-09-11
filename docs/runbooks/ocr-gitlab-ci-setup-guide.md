# OCR v2 — GitLab CI Setup Guide

**Data:** 2026-09-11  
**Status:** 🔧 Configuration Required  
**Timeline:** 15 minutes to complete  

---

## 🎯 Objetivo

Configurar as 3 variáveis necessárias no GitLab CI para fazer deploy automático de OCR v2 para Fly.io staging.

---

## 📋 Variáveis Necessárias

### 1️⃣ FLY_API_TOKEN

**O que é:** Token de autenticação do Fly.io para deployments  
**Tipo:** Variable  
**Scope:** main  
**Flags:** Masked ✓ Protected ✓  

**Como obter:**

1. Ir para: https://fly.io/account/access-tokens
2. Clicar em "+ Create API Token"
3. Nome: `reqsys-ocr-gitlab-ci`
4. Permissions: `deploy-apps` (mínimo necessário)
5. Copiar o token gerado (formato: `fm1_...`)

**Onde configurar:**
- GitLab: Settings > CI/CD > Variables > Add variable
- Variável: `FLY_API_TOKEN`
- Valor: `[Cole seu token do Fly.io aqui]`

---

### 2️⃣ OCR_DATA_ENCRYPTION_KEY ✅ Gerada

**O que é:** Chave de criptografia AES-256-GCM para dados OCR (32 bytes em Base64)  
**Tipo:** Variable  
**Scope:** main  
**Flags:** Masked ✓ Protected ✓  

**Valor gerado:** (executar script para regenerar se necessário)

```
h8WvWKaXtGICrDGaPzyWVU68VRJfcB46OA2c99LrZA4=
```

**Onde configurar:**
- GitLab: Settings > CI/CD > Variables > Add variable
- Variável: `OCR_DATA_ENCRYPTION_KEY`
- Valor: `h8WvWKaXtGICrDGaPzyWVU68VRJfcB46OA2c99LrZA4=`

**⚠️ IMPORTANTE:**
- Guarde esta chave de forma segura
- NÃO coloque em logs ou mensagens
- Use a mesma chave em staging e produção
- Para secret rotation: manter chave anterior como v1

---

### 3️⃣ SLACK_WEBHOOK_OCR

**O que é:** Webhook para notificações de deploy (sucesso/falha)  
**Tipo:** Variable  
**Scope:** main  
**Flags:** Masked ✓ Protected ✓  

**Como criar:**

1. Ir para: https://api.slack.com/apps
2. Selecionar seu app (ou criar novo)
3. Ir para: **Incoming Webhooks**
4. Clicar em **"Add New Webhook to Workspace"**
5. Selecionar o canal: `#ocr-deploys` (ou outro)
6. Copiar a URL (formato: `https://hooks.slack.com/services/T.../B.../...`)

**Onde configurar:**
- GitLab: Settings > CI/CD > Variables > Add variable
- Variável: `SLACK_WEBHOOK_OCR`
- Valor: `https://hooks.slack.com/services/T.../B.../...`

---

## 🚀 Passo a Passo de Configuração

### Passo 1: Abrir GitLab Settings

1. Ir para: https://gitlab.com/ericson-j-santos/reqsys-v2-enterprise-real
2. Clicar em: **Settings** (engrenagem no topo)
3. No menu esquerdo, clicar em: **CI/CD**
4. Expandir: **Variables**

### Passo 2: Adicionar FLY_API_TOKEN

1. Clicar em: **Add variable**
2. **Key:** `FLY_API_TOKEN`
3. **Value:** [Cole seu token do Fly.io]
4. **Type:** Variable
5. **Scope:** main
6. **Flags:** ✓ Masked, ✓ Protected
7. Clicar em: **Add variable**

### Passo 3: Adicionar OCR_DATA_ENCRYPTION_KEY

1. Clicar em: **Add variable**
2. **Key:** `OCR_DATA_ENCRYPTION_KEY`
3. **Value:** `h8WvWKaXtGICrDGaPzyWVU68VRJfcB46OA2c99LrZA4=`
4. **Type:** Variable
5. **Scope:** main
6. **Flags:** ✓ Masked, ✓ Protected
7. Clicar em: **Add variable**

### Passo 4: Adicionar SLACK_WEBHOOK_OCR

1. Clicar em: **Add variable**
2. **Key:** `SLACK_WEBHOOK_OCR`
3. **Value:** [Cole sua URL do Slack webhook]
4. **Type:** Variable
5. **Scope:** main
6. **Flags:** ✓ Masked, ✓ Protected
7. Clicar em: **Add variable**

### Resultado Final

Você deve ter 3 variáveis configuradas:

```
✓ FLY_API_TOKEN          [fm1_...]
✓ OCR_DATA_ENCRYPTION_KEY [h8WvWKaXtGICrDGaPzyWVU68VRJfcB46OA2c99LrZA4=]
✓ SLACK_WEBHOOK_OCR      [https://hooks.slack.com/services/...]
```

---

## ✅ Testar o Deploy

### 1. Ir para Pipelines

1. GitLab > **CI/CD** > **Pipelines**
2. Localizar seu pipeline (branch `main`)

### 2. Executar Deploy Job

1. Clicar no pipeline
2. Procurar pelo job: **ocr_deploy_staging_fly**
3. Clicar no botão: **Play** (▶)
4. Confirmar (se solicitado)

### 3. Aguardar Execução

O pipeline vai executar:
- **Stage: deploy** (2-3 min)
  - `ocr_deploy_staging_fly`: Deploy para Fly.io
- **Stage: validate** (2-3 min)
  - `ocr_validate_staging_readiness`: Validar OCR pronto
  - `ocr_validate_staging_health`: Health checks
  - `ocr_integration_tests_staging`: Testes OCR
- **Stage: evidence** (1 min)
  - `ocr_publish_staging_evidence`: Consolidar artefatos
  - `ocr_notify_slack_*`: Notificações Slack

**Total:** ~5-8 minutos

### 4. Validar Resultado

**✅ Se sucesso:**
- Job verde ✓
- Slack notification recebida
- URLs disponíveis:
  - Health: https://reqsys-api-stg.fly.dev/health
  - Readiness: https://reqsys-api-stg.fly.dev/v1/ocr/readiness
  - Metrics: https://reqsys-api-stg.fly.dev/metrics

**❌ Se falha:**
- Revisar logs do job
- Problemas comuns:
  - `FLY_API_TOKEN` inválido → Regenerar em Fly.io
  - `OCR_DATA_ENCRYPTION_KEY` vazio → Verificar configuração
  - `SLACK_WEBHOOK_OCR` inválido → Testar webhook no Slack

---

## 🔍 Verificar Deployment

### Logs do Pipeline

1. GitLab > CI/CD > Pipelines
2. Clicar no pipeline
3. Clicar no job `ocr_deploy_staging_fly`
4. Ver logs detalhados

### Verificar App em Fly.io

```bash
flyctl status --app reqsys-api-stg
```

Ou via web:
1. Ir para: https://fly.io/apps/reqsys-api-stg
2. Ver status da app e máquinas

### Verificar Endpoints

```bash
# Health check
curl https://reqsys-api-stg.fly.dev/health

# OCR readiness
curl https://reqsys-api-stg.fly.dev/v1/ocr/readiness

# Metrics
curl https://reqsys-api-stg.fly.dev/metrics
```

### Revisar Evidência

1. GitLab > CI/CD > Pipelines > Seu pipeline
2. Ir para: **Artifacts**
3. Download: `audit/ocr/staging-deploy-evidence.json`
4. Revisar conteúdo

---

## 🚨 Troubleshooting

### Job Fails: FLY_API_TOKEN

**Sintoma:** Erro na validação de variável  
**Solução:**
1. Verificar se variável existe em Settings > CI/CD > Variables
2. Regenerar token em: https://fly.io/account/access-tokens
3. Atualizar variável no GitLab

### Job Fails: Readiness Check

**Sintoma:** App deployada mas readiness = false  
**Solução:**
1. Verificar se `OCR_DATA_ENCRYPTION_KEY` foi passada corretamente
2. Revisar logs: `flyctl logs --app reqsys-api-stg`
3. Validar environment variables na app

### Job Fails: Slack Notification

**Sintoma:** Deploy ok mas Slack notification não chega  
**Solução:**
1. Testar webhook em: https://api.slack.com/apps > Incoming Webhooks
2. Verificar se URL webhook está correta
3. Conferir permissões do bot no Slack

### App Crashes After Deploy

**Sintoma:** Fly.io app inicia mas crasha  
**Solução:**
1. Ver logs: `flyctl logs --app reqsys-api-stg`
2. Verificar se todas as env vars estão configuradas
3. Testar build local: `docker build -t reqsys-ocr backend/`

---

## 📞 Próximas Ações

### Após Deploy com Sucesso

1. ✅ Validar endpoints acessíveis
2. ✅ Revisar Slack notifications
3. ✅ Documentar evidência
4. 📧 Sincronizar com DevOps sobre PC24x7 (ver: `ocr-deployment-action-items.md`)

### Antes de Production

1. Testar secret rotation workflow
2. Validar backup/recovery procedure
3. Configurar monitoring + alertas
4. Treinar team nos procedimentos

---

## 📚 Documentação Relacionada

- [OCR Deployment Strategy](ocr-deployment-strategy.md) — Visão geral dos 3 pilares
- [OCR PC24x7 Migration Plan](ocr-pc24x7-migration-plan.md) — Plano de migração
- [OCR Action Items](ocr-deployment-action-items.md) — Próximas ações
- [OCR Deploy Job](../../gitlab/ci/ocr-deploy-staging.yml) — Spec do job

---

## ⏱️ Timeline

| Etapa | Tempo |
|-------|-------|
| Configurar 3 variáveis | 5 min |
| Fazer merge no main | 1 min |
| Executar deploy job | 5-8 min |
| Validar endpoints | 2 min |
| Documentar evidência | 2 min |
| **Total** | **~20 min** |

---

**Status:** 🔧 Ready to configure  
**Responsável:** Team OCR  
**Data de atualização:** 2026-09-11
