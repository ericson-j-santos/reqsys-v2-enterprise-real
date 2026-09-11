# Email Template: PC24x7 Readiness Sync com DevOps

**Destinatário:** DevOps Team  
**Assunto:** Desbloquear PC24x7 para OCR v2 — Specs & Timeline Needed  
**Data:** 2026-09-11  

---

## 📧 Template do Email

```
Subject: Desbloquear PC24x7 para OCR v2 — Docker-compose & Specs Needed

Olá DevOps Team,

Estamos prontos para começar a migração de OCR v2 de Fly.io para PC24x7 
quando a infraestrutura estiver disponível.

SITUAÇÃO ATUAL:
═════════════════════════════════════════════════════════════════

Staging:    ✅ Fly.io (reqsys-api-stg) — Deploy via GitLab CI pronto
Production: ✅ Fly.io (reqsys-api) — Operacional
PC24x7:     ❌ Em migração, docker-compose vazio

CHECKLIST DE DESBLOQUEIADORES:
═════════════════════════════════════════════════════════════════

Para sair de "hold pattern" e começar Fase 1 (HML piloto):

Infra:
  [ ] docker-compose.hml.yml preenchido (com OCR backend + worker)
  [ ] docker-compose.prod.yml preenchido (HA setup com 3 replicas)
  [ ] Networking/load-balancer operacional
  [ ] Persistent volumes para OCR_INPUT_ROOT (/data/ocr-input)

Security:
  [ ] Vault/secrets management integrado (cofre corporativo)
  [ ] Segredos injetados: OCR_DATA_ENCRYPTION_KEY, DATABASE_URL, JWT_SECRET

Validação:
  [ ] Endpoints definidos (staging + prod URLs)
  [ ] Health check endpoints funcionando (/health, /v1/ocr/readiness)
  [ ] Monitoring/alerting configurado (Prometheus metrics)

DOCKER-COMPOSE TEMPLATE:
═════════════════════════════════════════════════════════════════

Template completo em: 
  docs/architecture/ocr-pc24x7-migration-plan.md (Seção "Fase 0")

Resumo:
- Backend: Python 3.11, porta 8211, 512MB RAM
- Worker: Processa jobs OCR async, reutiliza image
- Volumes: ocr_input_hml, ocr_data_hml (persistent)
- Healthcheck: GET /health (30s interval, 3 retries)
- Secrets: OCR_DATA_ENCRYPTION_KEY, DATABASE_URL, JWT_SECRET

PROPOSTAS PARALELAS:
═════════════════════════════════════════════════════════════════

Para não bloquear staging:
1. Manter Fly.io em produção por enquanto
2. Começar Fase 0 (PC24x7 prep) em paralelo
3. HML piloto (Fase 1) quando pronto
4. PROD canary (Fase 2) com 1-2 semanas de soak time
5. Cutover completo (Fase 3) após estável

Timeline: 8+ semanas após PC24x7 estar pronto

DOCUMENTAÇÃO:
═════════════════════════════════════════════════════════════════

Completa em:
  - docs/architecture/ocr-pc24x7-migration-plan.md (plano 3 fases)
  - docs/architecture/ocr-deployment-strategy.md (estratégia geral)
  - docs/runbooks/ocr-deployment-action-items.md (ações imediatas)

SOLICITUDES:
═════════════════════════════════════════════════════════════════

1. [ ] Confirmar PC24x7 timeline (eta para pronto?)
2. [ ] Enviar docker-compose template preenchido
3. [ ] Confirmar storage strategy (volumes)
4. [ ] Confirmar networking (endpoints staging/prod)
5. [ ] Integração com secrets vault (como passar OCR_DATA_ENCRYPTION_KEY?)
6. [ ] Call de alinhamento (30 min)?

PRÓXIMAS AÇÕES DO NOSSO LADO:
═════════════════════════════════════════════════════════════════

1. ✅ Deploy OCR v2 em Fly.io staging (pronto)
2. ✅ Criar plano de migração PC24x7 (pronto)
3. ⏳ Aguardar specs de PC24x7
4. 📅 Começar Fase 1 (HML piloto) quando pronto

Ficamos à disposição para:
- Revisar docker-compose files
- Validar secrets management
- Testar deployment no PC24x7
- Troubleshooting + rollback procedures

Vocês têm timeline e pode começar a trabalhar na Fase 0?

Abs,
Team OCR
```

---

## 📋 Checklist de Envio

- [ ] Copiar template acima
- [ ] Personalizar com emails reais do DevOps team
- [ ] Adicionar link para docs completas
- [ ] Enviar email
- [ ] Criar follow-up meeting (se necessário)
- [ ] Documentar respostas em wiki/board

---

## 🎯 Objetivos da Sincronização

1. **Comunicar status:** OCR pronto em Fly.io, PC24x7 em hold
2. **Solicitar specs:** Docker-compose, networking, storage, vault
3. **Alinhar timeline:** Quando PC24x7 pode estar pronto?
4. **Planejar Fase 0:** Preparação em paralelo
5. **Estabelecer contatos:** Quem é responsável por quê?

---

## 💬 Follow-up Se Não Tiver Resposta (1 semana depois)

```
Assunto: [FOLLOW-UP] Desbloquear PC24x7 para OCR v2 — Specs Needed

Olá,

Seguindo nosso email anterior sobre PC24x7 specs para OCR v2.

Conseguiram começar? Qual é o status?

Podemos agendar uma call rápida para alinhar:
1. Timeline de PC24x7
2. Responsáveis por cada componente
3. Docker-compose approach

Ficamos à disposição!

Abs,
Team OCR
```

---

## 📞 Se Necessário, Agendar Call

**Agenda sugerida para Call DevOps + OCR (30 min):**

1. Status PC24x7 (5 min)
2. Docker-compose review (10 min)
3. Networking & storage (5 min)
4. Secrets vault integration (5 min)
5. Timeline & blockers (5 min)

---

## 📎 Anexos para Incluir no Email

1. Link: `docs/architecture/ocr-pc24x7-migration-plan.md`
2. Link: `docs/architecture/ocr-deployment-strategy.md`
3. Link: `gitlab/ci/ocr-deploy-staging.yml`
4. PDF/Diagram: Migration 3 fases (se criar)

---

**Status:** 📧 Ready to send  
**Responsável:** Team OCR  
**Data:** 2026-09-11
