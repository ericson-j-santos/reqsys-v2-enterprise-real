# 📚 Guias — Documentação de Setup e Integração

Índice de guias práticos para desenvolvedores e operadores do ReqSys.

---

## 🔐 OCR v2 — Revisão Humana com Armazenamento Protegido

O OCR v2 do ReqSys processa documentos com **criptografia AES-256-GCM** e submete resultados de baixa confiança para **revisão humana governada**.

### 📖 Guias OCR

| Guia | Público | Descrição | Tempo |
|------|---------|-----------|-------|
| **[Setup Local Development](ocr-setup-local-development.md)** | 👨‍💻 Devs | Como configurar OCR em seu ambiente local | 5 min |
| **[Setup Checklist](../.github/OCRL_SETUP_CHECKLIST.md)** | ✅ Verificação | Checklist interativo antes de commitar | 2 min |
| **[Arquitetura OCR v2](../architecture/ocr-secure-review-v2.md)** | 🏗️ Arquitetos | Especificação técnica completa do bounded context | 20 min |

### 🚀 Quick Start (5 minutos)

```bash
# 1. Gerar chave de criptografia
python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# 2. Adicionar ao .env local
echo "OCR_DATA_ENCRYPTION_KEY=<chave-gerada>" >> .env
echo "OCR_INPUT_ROOT=C:/tmp/ocr-input" >> .env

# 3. Criar diretório
mkdir -p C:\tmp\ocr-input

# 4. Validar
.\scripts\validate-ocr-setup.ps1

# 5. Iniciar backend
docker-compose up -d backend
# ou: uvicorn app.main:app --reload --port 8211

# 6. Confirmar readiness
curl http://localhost:8211/v1/ocr/readiness
```

**Esperado:** `"ready": true`

### 🔗 Links Relacionados

- 📋 **Documentação de Arquitetura:** [docs/architecture/ocr-bounded-context.md](../architecture/ocr-bounded-context.md)
- 🧪 **Testes:** [backend/tests/test_ocr_review_api.py](../../backend/tests/test_ocr_review_api.py)
- 🔐 **Storage Protegido:** [backend/app/ocr/storage.py](../../backend/app/ocr/storage.py)
- 📊 **Workflows CI/CD:** `.github/workflows/ocr-*.yml`

---

## 📋 Outros Guias

*Adicione mais guias conforme o projeto evolui*

| Guia | Status |
|------|--------|
| Backend Setup | 📋 Planejado |
| Frontend Development | 📋 Planejado |
| Database Migrations | 📋 Planejado |
| Deployment (Fly.io) | 📋 Planejado |

---

## 🆘 Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| `OCR_STORE_NOT_READY` | Executar `.\scripts\validate-ocr-setup.ps1` |
| `key_configured: false` | Adicionar `OCR_DATA_ENCRYPTION_KEY` ao `.env` |
| `input_root_configured: false` | Criar diretório em `OCR_INPUT_ROOT` |
| Backend não responde | Verificar porta: `lsof -i :8211` |

---

## 📞 Suporte

- 🐛 **Bug ou problema?** Abra uma issue no GitHub
- 💬 **Dúvida?** Pergunte no Slack `#dev-ocr` ou `#dev-backend`
- 📧 **Feedback?** Comente no PR relacionado

---

**Última atualização:** 2026-09-11  
**Versão OCR:** v2 (AES-256-GCM)  
**Mantido por:** @ericson-j-santos + Team OCR
