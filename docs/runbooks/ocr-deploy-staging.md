# OCR v2 — Deploy para Staging

**Versão:** 1.0  
**Data:** 2026-09-11  
**Ambiente:** Fly.io  
**Responsável:** DevOps + Team OCR  

---

## 📋 Pre-Deploy Checklist

### Code Quality
- [ ] Todos os testes passando (`pytest backend/tests/test_ocr*.py`)
- [ ] Code review aprovado (GitHub PR)
- [ ] Sem secrets em código (`trufflesecurity scan`)
- [ ] Type checking limpo (`mypy backend/app/ocr/`)

### Documentation
- [ ] Guides atualizados
- [ ] Arquitetura documentada
- [ ] Changelog atualizado
- [ ] Runbooks atualizados

### Staging Environment
- [ ] Fly.io app `reqsys-api-staging` criado
- [ ] Database staging configurado
- [ ] Secrets configurados (veja seção abaixo)
- [ ] Volume para OCR_INPUT_ROOT montado

---

## 🔑 Configuração de Secrets (Staging)

### Criar secrets no Fly.io:

```bash
# Instalar Fly CLI se necessário
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login

# Gerar chave OCR v2 para staging
OCR_KEY=$(python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())")

# Configurar secrets
flyctl secrets set \
  OCR_DATA_ENCRYPTION_KEY="$OCR_KEY" \
  OCR_DATA_KEY_VERSION="v1" \
  OCR_INPUT_ROOT="/data/ocr-input" \
  DATABASE_URL="postgresql+psycopg2://..." \
  JWT_SECRET="..." \
  -a reqsys-api-staging

# Verificar
flyctl secrets list -a reqsys-api-staging
```

---

## 🚀 Deploy Steps

### 1. Preparar branch

```bash
# Garantir que estamos em main e atualizado
git checkout main
git pull origin main

# Verificar status
git log --oneline -5
```

### 2. Build Docker image

```bash
# Opção A: Deixar Fly.io fazer (automático)
# Opção B: Build local para testes

docker build -t reqsys-ocr:staging \
  -f Dockerfile \
  --build-arg ENV=staging \
  .

# Testar imagem localmente
docker run -e APP_ENV=staging \
  -e OCR_DATA_ENCRYPTION_KEY="$OCR_KEY" \
  -p 8211:8211 \
  reqsys-ocr:staging
```

### 3. Deploy para Staging

```bash
# Opção A: Deploy automático via Fly.io (recomendado)
flyctl deploy -a reqsys-api-staging

# Opção B: Deploy via GitHub Actions (se configurado)
# Vai automático ao fazer merge para main

# Monitorar deploy
flyctl status -a reqsys-api-staging
flyctl logs -a reqsys-api-staging --follow
```

### 4. Verificar Health

```bash
# Esperar 30-60 segundos para o app iniciar
sleep 60

# Health check
curl https://reqsys-api-staging.fly.dev/health

# OCR readiness check
curl https://reqsys-api-staging.fly.dev/v1/ocr/readiness

# Esperado:
# {
#   "ready": true,
#   "encryption": "AES-256-GCM",
#   "key_configured": true,
#   "input_root_configured": true,
#   "plaintext_storage_allowed": false
# }
```

---

## ✅ Post-Deploy Validation

### 1. Testes Básicos

```bash
# Verificar endpoints principais
curl -X GET https://reqsys-api-staging.fly.dev/health
curl -X GET https://reqsys-api-staging.fly.dev/v1/ocr/readiness

# Testar com token (se autenticado)
TOKEN="<seu-jwt-token>"
curl -X GET https://reqsys-api-staging.fly.dev/v1/ocr/readiness \
  -H "Authorization: Bearer $TOKEN"
```

### 2. Testes de Integração

```bash
# Executar suite de testes contra staging
pytest backend/tests/test_ocr_setup_integration.py \
  --env=staging \
  -v

# Ou via script
bash scripts/test-ocr-staging.sh
```

### 3. Testes Manual (UI)

```bash
# Acessar aplicação
https://reqsys-api-staging.fly.dev

# Testar fluxo OCR:
1. Acessar /admin/ocr-review
2. Status deve estar "Pronto" (não bloqueado)
3. Tentar upload de documento de teste
4. Verificar se processamento funciona
```

### 4. Monitoramento

```bash
# Ver logs em tempo real
flyctl logs -a reqsys-api-staging --follow

# Verificar métricas Prometheus
curl https://reqsys-api-staging.fly.dev/metrics | grep ocr_

# Esperado:
# ocr_readiness_status{environment="staging", component="encryption"} 1
# ocr_readiness_status{environment="staging", component="input_root"} 1
```

---

## 🔄 Rollback (Se Necessário)

### Quick Rollback

```bash
# Ver versões anteriores
flyctl releases -a reqsys-api-staging

# Revert para release anterior
flyctl releases rollback <RELEASE_ID> -a reqsys-api-staging

# Ou especificar versão anterior
flyctl deploy -a reqsys-api-staging --image reqsys/ocr:previous-tag
```

### Manualmente

```bash
# 1. Reverter commits se necessário
git revert <commit-hash>
git push origin main

# 2. Redeploy automático (ou manual)
flyctl deploy -a reqsys-api-staging

# 3. Reverter secrets se necessário
flyctl secrets set \
  OCR_DATA_ENCRYPTION_KEY="<chave-antiga>" \
  -a reqsys-api-staging
```

---

## 📊 Checklist de Sucesso

- [ ] Deploy completo sem erros
- [ ] App iniciando corretamente
- [ ] Health check respondendo
- [ ] OCR readiness = true
- [ ] Metrics sendo exportados
- [ ] Logs sendo coletados
- [ ] Testes passando
- [ ] UI acessível
- [ ] Documento teste processado
- [ ] Nenhum error em logs

---

## 🆘 Troubleshooting

### "Ready: false" na readiness check

```bash
# Verificar se secrets estão configurados
flyctl secrets list -a reqsys-api-staging

# Verificar logs
flyctl logs -a reqsys-api-staging | grep OCR

# Solução: Re-aplicar secrets
flyctl secrets set OCR_DATA_ENCRYPTION_KEY="$OCR_KEY" -a reqsys-api-staging
```

### "Connection refused" em localhost:8211

```bash
# Esperado! App está em https://reqsys-api-staging.fly.dev
# Não em localhost

# Acessar corretamente:
curl https://reqsys-api-staging.fly.dev/v1/ocr/readiness
```

### Deploy timeout

```bash
# Aumentar timeout
flyctl deploy -a reqsys-api-staging --wait-timeout 300

# Ou monitorar logs
flyctl logs -a reqsys-api-staging --follow
```

### Database connection error

```bash
# Verificar string de conexão
flyctl secrets list -a reqsys-api-staging | grep DATABASE

# Testar conexão
flyctl ssh console -a reqsys-api-staging
# Dentro do container:
# psql $DATABASE_URL
```

---

## 📞 Contatos

- **DevOps Lead:** @ericson-j-santos
- **Team OCR:** #dev-ocr Slack
- **Incidents:** Page on-call via Alertmanager

---

## 📝 Log de Deploys

| Data | Versão | Status | Responsável | Notas |
|------|--------|--------|-------------|-------|
| 2026-09-11 | 1.0 | Planejado | ericson-j-santos | Deploy inicial staging |

---

**Template criado:** 2026-09-11  
**Última atualização:** 2026-09-11
