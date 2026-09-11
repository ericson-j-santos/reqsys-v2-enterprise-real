# OCR v2 — Automated GitLab CI Setup

**Data:** 2026-09-11  
**Status:** 🤖 Fully Automated  
**Tempo:** ~2 minutos (vs 20 minutos manual)  

---

## 🚀 Como Funciona

O script PowerShell `setup-ocr-gitlab-ci-automatic.ps1` automatiza **100% do processo**:

```
✅ Validar GitLab token
✅ Criar/atualizar 3 variáveis de CI/CD
✅ Validar configuração final
✅ Opcionalmente, disparar pipeline
```

**Requisitos:**
- PowerShell 5.0+
- Acesso de internet
- GitLab Personal Access Token (glpat-...)
- Fly.io API Token (fm1_...) — opcional
- Slack Webhook URL — opcional

---

## 📋 Passo 1: Obter Credenciais

### GitLab Personal Access Token (obrigatório)

1. Ir para: https://gitlab.com/-/user_settings/personal_access_tokens
2. Clicar em: "+ Create personal access token"
3. Nome: `ocr-gitlab-ci-setup`
4. Scopes: ✓ api, ✓ read_api
5. Expiration: 30 dias (suficiente para setup)
6. **Copiar o token** (formato: `glpat-...`)

**⚠️ Não compartilhe este token!**

### Fly.io API Token (opcional, mas recomendado)

1. Ir para: https://fly.io/account/access-tokens
2. Clicar em: "+ Create API Token"
3. Nome: `reqsys-ocr-gitlab-ci`
4. Permissions: `deploy-apps`
5. **Copiar o token** (formato: `fm1_...`)

Se não tiver, pode fornecer depois e o script vai pedir.

### Slack Webhook URL (opcional)

1. Ir para: https://api.slack.com/apps
2. Selecionar seu app (ou criar novo)
3. Ir para: **Incoming Webhooks**
4. Clicar em: **"Add New Webhook to Workspace"**
5. Selecionar canal: `#ocr-deploys`
6. **Copiar a URL** (formato: `https://hooks.slack.com/...`)

Se não tiver, pode fornecer depois e o script vai pedir.

---

## 🎯 Passo 2: Executar Script

### Opção A: Modo Interativo (Recomendado)

```powershell
cd C:\dev\reqsys-v2-enterprise-real
.\scripts\setup-ocr-gitlab-ci-automatic.ps1 -GitLabToken 'glpat-xxxxxxxxxxxx'
```

O script vai pedir os outros tokens interativamente.

### Opção B: Modo Completo (Uma linha)

```powershell
.\scripts\setup-ocr-gitlab-ci-automatic.ps1 `
  -GitLabToken 'glpat-xxxxxxxxxxxx' `
  -FlyToken 'fm1_xxxxxxxxxxxx' `
  -SlackWebhook 'https://hooks.slack.com/services/T../B../...'
```

### Opção C: Modo Validação (Sem alterações)

Verificar se tudo já está configurado:

```powershell
.\scripts\setup-ocr-gitlab-ci-automatic.ps1 -GitLabToken 'glpat-xxxxxxxxxxxx' -ValidateOnly
```

### Opção D: Modo Dry-Run (Simular)

Ver o que seria feito sem fazer nada:

```powershell
.\scripts\setup-ocr-gitlab-ci-automatic.ps1 -GitLabToken 'glpat-xxxxxxxxxxxx' -DryRun
```

---

## 📊 Exemplo de Execução

```
════════════════════════════════════════════════════════════════
  OCR v2 — GitLab CI Setup Automation
════════════════════════════════════════════════════════════════

📝 Modo: NORMAL (alterações reais)

🔑 GitLab Personal Access Token (obter em: https://gitlab.com/-/user_settings/personal_access_tokens)
Token (glpat-...): glpat_abc123xyz...

🔑 Fly.io API Token (obter em: https://fly.io/account/access-tokens)
Token (fm1_...) [Enter para pular]: fm1_abc123xyz...

🔑 Slack Webhook URL (obter em: https://api.slack.com/apps > Incoming Webhooks)
URL (https://hooks.slack.com/...) [Enter para pular]: https://hooks.slack.com/services/T.../B.../...

🔍 Testando GitLab token...
✅ Token válido. Usuário: ericson-j-santos

⚙️  Configurando variáveis GitLab...
➕ Criando variável: FLY_API_TOKEN
✅ Variável criada: FLY_API_TOKEN

➕ Criando variável: OCR_DATA_ENCRYPTION_KEY
✅ Variável criada: OCR_DATA_ENCRYPTION_KEY

➕ Criando variável: SLACK_WEBHOOK_OCR
✅ Variável criada: SLACK_WEBHOOK_OCR

✅ Validando configuração final...
📋 Validando configuração...
✅ FLY_API_TOKEN: Configurada (Masked: True, Protected: True)
✅ OCR_DATA_ENCRYPTION_KEY: Configurada (Masked: True, Protected: True)
✅ SLACK_WEBHOOK_OCR: Configurada (Masked: True, Protected: True)

✅ Todas as variáveis configuradas!

════════════════════════════════════════════════════════════════
✅ SUCESSO! Todas as variáveis configuradas no GitLab

Próximas ações:
  1. Ir para: https://gitlab.com/ericson-j-santos/reqsys-v2-enterprise-real/pipelines
  2. Clicar em: ▶️ Play no job 'ocr_deploy_staging_fly'
  3. Aguardar ~5-8 minutos
  4. Validar endpoints:
     - https://reqsys-api-stg.fly.dev/health
     - https://reqsys-api-stg.fly.dev/v1/ocr/readiness

📚 Documentação: https://gitlab.com/ericson-j-santos/reqsys-v2-enterprise-real/tree/main/docs/runbooks
════════════════════════════════════════════════════════════════
```

---

## 🔒 Segurança

### Boas Práticas

✅ **Use o token apenas durante o setup**
- Após executar o script, o token pode ser descartado
- Revogar token em: https://gitlab.com/-/user_settings/personal_access_tokens

✅ **Não coloque credenciais em scripts**
- O script **PEDE** os tokens interativamente
- Tokens **NÃO são salvos** em arquivos

✅ **Use variáveis Masked e Protected**
- Todas as variáveis são criadas com estes flags
- Valores não aparecem em logs

### Se algo der errado

❌ **Token foi exposto?**
1. Revogue imediatamente em GitLab
2. Criar novo token
3. Executar script novamente

❌ **Variável foi configurada errada?**
```powershell
# Simplesmente executar script novamente — vai sobrescrever
.\scripts\setup-ocr-gitlab-ci-automatic.ps1 -GitLabToken 'glpat-...'
```

---

## 🎯 Próximas Ações Após Setup

### 1. Testar Pipeline (5-8 min)

```
GitLab > CI/CD > Pipelines > Play ocr_deploy_staging_fly
```

### 2. Validar Endpoints

```bash
# Health
curl https://reqsys-api-stg.fly.dev/health

# Readiness
curl https://reqsys-api-stg.fly.dev/v1/ocr/readiness

# Metrics
curl https://reqsys-api-stg.fly.dev/metrics
```

### 3. Enviar Email DevOps

Usar template de: `docs/runbooks/devops-sync-email-template.md`

---

## ⚡ Modo Totalmente Automático

Se quiser fazer **TUDO** em um único comando:

```powershell
# Setup + Pipeline trigger (você ainda precisa de tokens)
.\scripts\setup-ocr-gitlab-ci-automatic.ps1 `
  -GitLabToken 'glpat-...' `
  -FlyToken 'fm1_...' `
  -SlackWebhook 'https://hooks.slack.com/...' `
  -TriggerPipeline
```

**Timeline:**
- Setup: ~1 minuto
- Pipeline: ~5-8 minutos
- Total: ~10 minutos

---

## 📊 Comparação: Manual vs Automático

| Ação | Manual | Automático |
|------|--------|-----------|
| Navegar GitLab Settings | 1 min | 0 min |
| Adicionar 3 variáveis | 5 min | 1 min |
| Validar configuração | 2 min | Auto |
| Testar pipeline | 5-8 min | 5-8 min |
| **Total** | **~20 min** | **~10 min** |

**Economia: 50% do tempo!** ⚡

---

## 🚨 Troubleshooting

### ❌ "Token inválido"

```
❌ Token inválido ou expirado
```

**Solução:**
1. Verificar se token está correto (copiar novamente)
2. Verificar se token não expirou
3. Gerar novo token se necessário

### ❌ "Project not found"

```
❌ Erro ao criar variável: Not Found
```

**Solução:**
1. Verificar Project ID (48896143)
2. Verificar se você tem acesso ao projeto
3. Verificar se token tem scope `api`

### ❌ "Permission denied"

```
❌ Erro ao criar variável: 403 Forbidden
```

**Solução:**
1. Token precisa de scope `api`
2. Regenerar token com scopes corretos
3. Executar script novamente

---

## 📚 Documentação Relacionada

- [OCR GitLab CI Setup Guide](ocr-gitlab-ci-setup-guide.md) — Manual step-by-step
- [OCR Deployment Action Items](ocr-deployment-action-items.md) — Próximas ações
- [OCR Deployment Strategy](../architecture/ocr-deployment-strategy.md) — Estratégia geral
- [Setup Script Source](../../scripts/setup-ocr-gitlab-ci-automatic.ps1) — Código do script

---

## 🎯 Summary

```
✅ Script automatizado: setup-ocr-gitlab-ci-automatic.ps1
✅ Configura 3 variáveis em <2 minutos
✅ Validação automática
✅ Seguro (tokens não são salvos)
✅ Reversível (pode rodar novamente)
✅ Economia de 50% do tempo
```

**Próximo passo:** Execute o script!

```powershell
cd C:\dev\reqsys-v2-enterprise-real
.\scripts\setup-ocr-gitlab-ci-automatic.ps1 -GitLabToken 'glpat-...'
```

---

**Status:** 🤖 Ready to automate  
**Requisitos:** GitLab Personal Access Token  
**Tempo:** ~2 minutos  
**Data:** 2026-09-11
