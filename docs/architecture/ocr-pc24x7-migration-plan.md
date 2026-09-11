# OCR v2 — Plano de Migração para PC24x7

**Versão:** 1.0  
**Data:** 2026-09-11  
**Status:** 📋 Planejamento  
**Timeline:** TBD (depende de PC24x7 estar pronto)  

---

## 🎯 Objetivo

Migrar infraestrutura OCR v2 de **Fly.io → PC24x7** quando ambiente estiver disponível e configurado.

**Não bloqueia:** Staging em Fly.io continua operacional.

---

## 📊 Estado Atual

| Aspecto | Status |
|---------|--------|
| **Staging** | ✅ Fly.io (reqsys-api-stg) |
| **Production** | ✅ Fly.io (reqsys-api) |
| **PC24x7** | ❌ Em migração, docker-compose vazios |
| **Timeline** | ⏳ Aguardando specs de PC24x7 |

---

## 🔄 Fases de Migração

### Fase 0: Preparação (Paralelo com Fly.io)

**Status:** 📋 Em andamento

Checklist:
- [ ] PC24x7 docker-compose configurado (HML + PROD)
- [ ] PC24x7 networking/loadbalancer pronto
- [ ] PC24x7 persistent volumes para OCR_INPUT_ROOT
- [ ] PC24x7 secrets management (vault/cofre)
- [ ] PC24x7 endpoints definidos (staging/prod URLs)
- [ ] PC24x7 health check endpoints validados

**Bloqueadores:**
- Docker-compose.hml.yml vazio
- Docker-compose.prod.yml vazio
- Sem endpoint definido
- Sem secrets strategy

---

### Fase 1: Staging Piloto (PC24x7 HML)

**Timeline:** Após PC24x7 pronto

1. **Build & Push**
   ```bash
   docker build -t reqsys-ocr:pc24x7-hml \
     --build-arg ENV=staging \
     -f backend/Dockerfile backend/
   
   docker push registry/reqsys-ocr:pc24x7-hml
   ```

2. **Deploy em PC24x7 HML**
   ```bash
   # Usar docker-compose.hml.yml (quando configurado)
   docker-compose -f docker-compose.hml.yml \
     -e OCR_DATA_ENCRYPTION_KEY="$KEY" \
     up -d ocr-backend
   ```

3. **Validação**
   ```bash
   # Endpoints de saúde
   curl http://pc24x7-hml/health
   curl http://pc24x7-hml/v1/ocr/readiness
   
   # Testes
   pytest tests/test_ocr_setup_integration.py
   ```

4. **Rollback Plan**
   - Continue com Fly.io se falhar
   - Mantenha ambos rodando em paralelo por 1-2 semanas

---

### Fase 2: Production Canary (PC24x7 PROD)

**Timeline:** Após Fase 1 passar 1-2 semanas

1. **Canary Deploy** (5% → 25% → 100%)
   ```bash
   # Usar docker-compose.prod.yml
   docker-compose -f docker-compose.prod.yml \
     scale ocr-backend=3  # HA setup
   ```

2. **Monitoramento**
   - Métricas Prometheus (ocr_*)
   - Logs agregados
   - Alertas habilitados
   - Error rate < 0.1%

3. **Rollback Trigger**
   - Error rate > 1%
   - Latência P99 > 1s
   - OCR readiness = false

---

### Fase 3: Desligar Fly.io (PC24x7 PROD Stable)

**Timeline:** Após Fase 2 passar 2-4 semanas

1. **Validações Finais**
   - Zero Fly.io traffic por 1 semana
   - Todos os dados migrados
   - Compliance validado

2. **Cleanup Fly.io**
   ```bash
   flyctl apps destroy reqsys-api-stg --yes
   flyctl apps destroy reqsys-api --yes
   ```

3. **Arquivamento**
   - Documentar Fly.io config
   - Guardar scripts históricos
   - Update runbooks

---

## 🔑 Configuração Necessária em PC24x7

### Docker Compose (HML)

**Arquivo:** `docker-compose.hml.yml`

```yaml
version: '3.8'

services:
  ocr-backend:
    image: reqsys/backend:${OCR_VERSION:-latest}
    build:
      context: backend/
      dockerfile: Dockerfile
      args:
        ENV: staging
    ports:
      - "8211:8211"
    environment:
      - APP_ENV=staging
      - OCR_DATA_ENCRYPTION_KEY=${OCR_DATA_ENCRYPTION_KEY}
      - OCR_DATA_KEY_VERSION=${OCR_DATA_KEY_VERSION:-v1}
      - OCR_INPUT_ROOT=/data/ocr-input
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET=${JWT_SECRET}
    volumes:
      - ocr_input_hml:/data/ocr-input
      - ocr_data_hml:/data/ocr-storage
    networks:
      - reqsys-hml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8211/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    
  ocr-worker:
    image: reqsys/backend:${OCR_VERSION:-latest}
    depends_on:
      - ocr-backend
    environment:
      - WORKER_TYPE=ocr
      - OCR_DATA_ENCRYPTION_KEY=${OCR_DATA_ENCRYPTION_KEY}
    volumes:
      - ocr_input_hml:/data/ocr-input
    networks:
      - reqsys-hml
    restart: unless-stopped

volumes:
  ocr_input_hml:
  ocr_data_hml:

networks:
  reqsys-hml:
    driver: bridge
```

### Secrets Management

**Localização:** Cofre corporativo (não .env commitado)

```
OCR_DATA_ENCRYPTION_KEY     ← 32 bytes Base64
OCR_DATA_KEY_VERSION         ← v1
DATABASE_URL                 ← PostgreSQL HML
JWT_SECRET                   ← JWT signing key
```

---

## 📋 Critérios de Sucesso

### Por Fase

| Fase | Critério | Métrica |
|------|----------|---------|
| **0** | PC24x7 pronto | Docker-compose completo |
| **1** | HML estável | Readiness=true por 1 semana |
| **2** | PROD canary | Error rate < 0.1% por 2 semanas |
| **3** | Cutover completo | Zero Fly.io traffic |

---

## 🔄 Rollback Strategy

**Se qualquer fase falhar:**

1. **HML (Fase 1 falha)**
   ```bash
   # Continuar com Fly.io
   # PC24x7 HML fica em staging-experimental
   # Retry após investigação
   ```

2. **PROD Canary (Fase 2 falha)**
   ```bash
   # Reverter traffic para Fly.io
   docker-compose -f docker-compose.prod.yml down
   # Manter PC24x7 para investigação pós-mortem
   ```

3. **PROD Stable (Fase 3 durante cutover)**
   ```bash
   # Scale down PC24x7
   # Re-enable Fly.io
   # 2-4 week retry
   ```

---

## 📞 Dependências Externas

| Item | Responsável | Status |
|------|-------------|--------|
| PC24x7 docker-compose | DevOps | ❌ Aguardando |
| PC24x7 networking | DevOps | ❌ Aguardando |
| PC24x7 storage | DevOps | ❌ Aguardando |
| PC24x7 secrets vault | Security | ❌ Aguardando |
| OCR team approval | Team OCR | ⏳ Pronto |

---

## 🎯 Próximas Ações

### Imediato
- [ ] Confirmar PC24x7 timeline com DevOps
- [ ] Revisar docker-compose template
- [ ] Documentar endpoints PC24x7 (quando disponíveis)
- [ ] Validar networking/storage requisitos

### Quando PC24x7 pronto
- [ ] Preencher docker-compose.hml.yml
- [ ] Configurar secrets vault
- [ ] Testar build/push de imagens
- [ ] Executar Fase 1 (HML)

---

## 📚 Referências

**Docs:**
- `docs/architecture/ocr-secure-review-v2.md` — OCR spec
- `docs/runbooks/ocr-deploy-staging.md` — Deploy atual
- `gitlab/ci/ocr-deploy-staging.yml` — GitLab job

**Specs PC24x7:** (TBD — aguardando DevOps)

---

**Status:** ⏳ Aguardando PC24x7  
**Próxima Review:** 2026-09-25  
**Responsável:** Team OCR + DevOps
