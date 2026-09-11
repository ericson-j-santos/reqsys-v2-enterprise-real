# OCR v2 — Production Hardening Checklist

**Versão:** 1.0  
**Data:** 2026-09-11  
**Status:** 📋 Planned (Fase 3)  
**Responsável:** Team OCR + DevOps  

---

## 📋 Resumo

Este documento define o plano de hardening do OCR v2 para produção, cobrindo:
- 🔐 Segurança (criptografia, vault, KMS)
- 📊 Observabilidade (logging, auditing)
- 🛡️ Resiliência (backup, disaster recovery)
- ⚡ Performance (caching, optimization)

---

## 🔐 Segurança

### 1. Vault Integration (Azure Key Vault)

**Status:** 📋 Planejado  
**Prioridade:** 🔴 Alta  
**Estimativa:** 3 horas  

**Objetivo:** Remover secrets de Fly.io, usar Azure Key Vault centralizado

**Checklist:**
- [ ] Criar vault resource em Azure
- [ ] Configurar acesso RBAC para aplicação
- [ ] Armazenar `OCR_DATA_ENCRYPTION_KEY` no vault
- [ ] Implementar client Azure SDK no backend
- [ ] Testar decrypt/encrypt com chave do vault
- [ ] Remover chaves de Fly.io secrets
- [ ] Verificar audit logs (quem acessou a chave)

**Implementação:**
```python
# backend/app/core/vault.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

class AzureVault:
    def __init__(self):
        vault_url = os.getenv("AZURE_VAULT_URL")
        credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=credential)
    
    def get_ocr_key(self, version: str = "v1") -> str:
        secret_name = f"OCR-DATA-ENCRYPTION-KEY-{version}"
        return self.client.get_secret(secret_name).value
```

---

### 2. KMS Encryption at Rest

**Status:** 📋 Planejado  
**Prioridade:** 🔴 Alta  
**Estimativa:** 4 horas  

**Objetivo:** Criptografar dados OCR em repouso com envelope encryption

**Checklist:**
- [ ] Provisionar Azure Key Encryption Key (KEK)
- [ ] Implementar envelope encryption (data key + KEK)
- [ ] Atualizar schema OCR para campo `kek_version`
- [ ] Testar round-trip: encrypt → store → retrieve → decrypt
- [ ] Migração: re-encriptar dados existentes
- [ ] Monitorar performance (overhead de KMS)

**Arquitetura:**
```
Plaintext OCR → Generate data_key → Encrypt with data_key → Store
                                ↓
                         Encrypt data_key with KEK
                         Store encrypted_data_key

Retrieve → Decrypt data_key with KEK → Decrypt plaintext
```

---

### 3. Network Security

**Status:** 📋 Planejado  
**Prioridade:** 🟠 Média  
**Estimativa:** 2 horas  

**Checklist:**
- [ ] Private endpoint para OCR_INPUT_ROOT (não expor em internet)
- [ ] Network policies: apenas backend → input directory
- [ ] TLS 1.3 para comunicação intra-cluster
- [ ] Mutual TLS (mTLS) entre serviços
- [ ] WAF rules para `/v1/ocr/*` endpoints
- [ ] Rate limiting por IP/token

**Implementação:**
```yaml
# kubernetes/ocr-network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ocr-input-access
spec:
  podSelector:
    matchLabels:
      app: reqsys-backend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: reqsys-backend
      ports:
        - protocol: TCP
          port: 8211
```

---

## 📊 Observabilidade & Auditing

### 4. Audit Logging

**Status:** 📋 Planejado  
**Prioridade:** 🔴 Alta  
**Estimativa:** 3 horas  

**Objetivo:** Registrar TODAS as operações sensíveis para compliance

**Checklist:**
- [ ] Log de acesso a `/v1/ocr/*` (who, when, what)
- [ ] Log de decrypt de dados (identidade revisor)
- [ ] Log de secret rotation (data, executor)
- [ ] Log de re-encryption jobs
- [ ] Armazenar logs em imutável (Azure Blob Archive)
- [ ] Integração com SIEM (Splunk/Sentinel)

**Schema de Auditoria:**
```json
{
  "timestamp": "2026-09-11T10:30:00Z",
  "operation": "ocr.decrypt",
  "user_id": "sha256(reviewer-email)",
  "job_id": "ocr-12345",
  "status": "success",
  "duration_ms": 145,
  "environment": "production"
}
```

---

### 5. Alerting & Monitoring

**Status:** 📋 Planejado  
**Prioridade:** 🟠 Média  
**Estimativa:** 2 horas  

**Alertas Críticos:**
- [ ] OCR readiness = false (degradação)
- [ ] Encryption errors > 5/min (falha de KMS)
- [ ] Re-encryption job failed (migração interrupted)
- [ ] Audit log lag > 5min (logging falhou)
- [ ] Secret rotation failed (missing v2 key)

**Implementação Prometheus:**
```yaml
# Alertas
- alert: OCRNotReady
  expr: ocr_readiness_status == 0
  for: 5m
  annotations:
    summary: "OCR não está pronto"
    action: "Verificar logs, reiniciar se necessário"

- alert: EncryptionErrors
  expr: rate(ocr_encryption_errors_total[5m]) > 0.1
  annotations:
    summary: "Taxa de erro de criptografia elevada"
    action: "Verificar Azure KMS connectivity"
```

---

## 🛡️ Resiliência

### 6. Backup & Disaster Recovery

**Status:** 📋 Planejado  
**Prioridade:** 🟠 Média  
**Estimativa:** 2 horas  

**Checklist:**
- [ ] Backup diário de OCR_INPUT_ROOT (Azure Blob)
- [ ] Backup de keys (vault-to-vault replication)
- [ ] RTO: 4 horas (recovery point)
- [ ] RPO: 24 horas (acceptable data loss)
- [ ] Teste de restore mensal
- [ ] Documentação de disaster recovery

**Plano de Contingência:**
```
Cenário: Perda de dados OCR
├─ Detectado: Monitoring alert
├─ Acionado: On-call engineer
├─ Ação 1: Pausar novos jobs OCR
├─ Ação 2: Restore blob backup
├─ Ação 3: Verificar integridade
├─ Ação 4: Re-encriptar if necessary
└─ Resolução: ~2 horas
```

---

### 7. High Availability

**Status:** 📋 Planejado  
**Prioridade:** 🟠 Média  
**Estimativa:** 3 horas  

**Checklist:**
- [ ] OCR worker replicas: 3+ (zero downtime deploys)
- [ ] Input directory em shared storage (NFS/SMB)
- [ ] Database read replicas (para readiness checks)
- [ ] Circuit breaker para KMS failures (fallback?)
- [ ] Load balancer health checks
- [ ] Graceful shutdown timeout: 30s

---

## ⚡ Performance & Optimization

### 8. Caching Strategy

**Status:** 📋 Planejado  
**Prioridade:** 🟡 Baixa  
**Estimativa:** 2 horas  

**Objetivo:** Reduzir latência de readiness checks

**Checklist:**
- [ ] Cache readiness status (TTL: 30s)
- [ ] Cache document metadata (TTL: 5min)
- [ ] Redis cluster para distributed cache
- [ ] Invalidate on secret rotation

---

### 9. Performance Tuning

**Status:** 📋 Planejado  
**Prioridade:** 🟡 Baixa  
**Estimativa:** 1 hora  

**Checklist:**
- [ ] Database query optimization (explain plans)
- [ ] Connection pooling (OCR → DB)
- [ ] Batch encryption for bulk operations
- [ ] Async processing for heavy workloads

---

## 📋 Pre-Production Validation

### Checklist Final

**Antes de fazer push para produção:**

- [ ] **Segurança**
  - [ ] Sem hardcoded secrets
  - [ ] Chaves em Azure Vault
  - [ ] Encryption at rest ativo
  - [ ] Audit logs coletando

- [ ] **Observabilidade**
  - [ ] Métricas sendo exportadas
  - [ ] Alertas testados
  - [ ] Logs sendo armazenados
  - [ ] Dashboard visível

- [ ] **Resiliência**
  - [ ] Backup testado
  - [ ] Disaster recovery documentado
  - [ ] HA setup validado
  - [ ] Failover testado

- [ ] **Performance**
  - [ ] Latência aceitável (< 500ms readiness)
  - [ ] Throughput: 100+ jobs/min
  - [ ] Cache working
  - [ ] No memory leaks

- [ ] **Compliance**
  - [ ] GDPR: PII criptografado
  - [ ] Audit log: 100% coverage
  - [ ] Retention: configurable
  - [ ] Access control: RBAC

---

## 🚀 Rollout Plan

### Stage 1: Staging (Week 1)
```
Deploy → Validate → Load test → Penetration test
```

### Stage 2: Canary (Week 2)
```
5% traffic → Monitor 24h → 25% traffic → Monitor 24h → 100%
```

### Stage 3: Production (Week 3)
```
Full deployment → Monitor 7 days → Celebrate 🎉
```

---

## 📞 Suporte

**Time Responsável:** Team OCR + DevOps  
**Escalation:** @ericson-j-santos  
**Status Page:** https://status.reqsys.prod/ocr  
**Runbook:** docs/runbooks/ocr-incidents.md  

---

## 📈 Success Metrics

| Métrica | Target | Current |
|---------|--------|---------|
| **Uptime** | 99.95% | -- |
| **P99 Latency** | < 500ms | -- |
| **Error Rate** | < 0.1% | -- |
| **Security** | 100% encrypted | ⏳ Vault pending |
| **Audit Coverage** | 100% logged | ⏳ Logging pending |

---

**Próxima Review:** 2026-09-25  
**Última Atualização:** 2026-09-11
