# OCR — Guia de Setup Desenvolvimento Local

**Versão:** 2.0 (AES-256-GCM secure review)  
**Data:** 2026-09-10  
**Status:** ✅ Pronto para integração

---

## 📋 Resumo Executivo

O **OCR v2** do ReqSys processa documentos com armazenamento protegido e revisão humana governada. Antes de trabalhar com OCR localmente, é necessário:

1. **Gerar chave de criptografia** (32 bytes Base64)
2. **Configurar variáveis de ambiente** (`.env`)
3. **Criar diretório de entrada** (`OCR_INPUT_ROOT`)
4. **Validar readiness** (`/v1/ocr/readiness`)

**Tempo estimado:** 5 minutos

---

## 🔐 Configuração Obrigatória

### Passo 1: Gerar Chave de Criptografia

Execute **fora do repositório** (não comitar em git):

```bash
# Linux/macOS
python3 -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# Windows PowerShell
python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

**Saída esperada:** String Base64 com ~43-44 caracteres  
**Exemplo:** `xBYqAcphzq3OohMcVlMhIMWgh2FfmdHArgWwYyjGncQ=`

⚠️ **Importante:** A saída é sensível — armazene apenas em `.env` ou secrets manager, nunca em logs/git.

### Passo 2: Configurar `.env` Local

Copie `.env.example` e adicione as variáveis OCR:

```bash
cp .env.example .env
```

Adicione ao final do arquivo `.env`:

```env
# OCR — Revisão humana com armazenamento protegido
OCR_DATA_ENCRYPTION_KEY=<cola-aqui-a-chave-gerada-no-passo-1>
OCR_DATA_KEY_VERSION=v1
OCR_INPUT_ROOT=C:/tmp/ocr-input
```

**Validação:** Verifique que `.env` **não** é commitado:

```bash
git check-ignore .env  # Deve retornar ".env" (indicando estar em .gitignore)
```

### Passo 3: Criar Diretório de Entrada

```bash
# Windows (PowerShell)
mkdir -Force C:\tmp\ocr-input

# Linux/macOS
mkdir -p /tmp/ocr-input
chmod 700 /tmp/ocr-input
```

Verifique acessibilidade:

```bash
ls -la C:\tmp\ocr-input  # Windows
ls -la /tmp/ocr-input    # Linux/macOS
```

---

## ✅ Validação de Configuração

### Validação Rápida (Local)

Execute o script de validação:

```bash
# Windows PowerShell
.\scripts\validate-ocr-setup.ps1

# Saída esperada:
# ========================================
#   Resultado: 4/4 checks passaram
# ========================================
# 🎉 Todas as verificações passaram! OCR pronto para uso.
```

### Validação com Backend Rodando

**1. Iniciar backend (escolha uma opção):**

**Opção A: Docker Compose**
```bash
docker-compose up -d backend
```

**Opção B: Python local (venv)**
```bash
cd backend
source .venv/Scripts/Activate.ps1  # Windows
# ou: source .venv/bin/activate     # Linux/macOS

uvicorn app.main:app --reload --port 8211
```

**2. Validar endpoint `/v1/ocr/readiness`:**

```bash
# Sem autenticação (desenvolvimento)
curl -X GET http://localhost:8211/v1/ocr/readiness

# Com token JWT (se exigido)
curl -X GET http://localhost:8211/v1/ocr/readiness \
  -H "Authorization: Bearer <seu-token>"
```

**Resposta esperada (readiness OK):**

```json
{
  "ready": true,
  "encryption": "AES-256-GCM",
  "key_configured": true,
  "input_root_configured": true,
  "plaintext_storage_allowed": false
}
```

**Se retornar `"ready": false`:**

| Campo | Solução |
|-------|---------|
| `key_configured: false` | Verifique `OCR_DATA_ENCRYPTION_KEY` em `.env` |
| `input_root_configured: false` | Verifique diretório em `OCR_INPUT_ROOT` |
| `plaintext_storage_allowed: true` | ⚠️ Falha crítica — OCR desabilitado por segurança |

Consulte logs do backend para detalhes:

```bash
docker-compose logs backend       # Docker
# ou verifique console do uvicorn # Python local
```

---

## 🧪 Testes End-to-End

### Teste 1: Upload de Documento Sintético

```bash
# 1. Criar documento de teste
echo "TESTE DE DOCUMENTO OCR" > C:\tmp\ocr-input\test-001.txt

# 2. Enviar job OCR via API
curl -X POST http://localhost:8211/v1/ocr/jobs \
  -H "Authorization: Bearer <seu-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "documento_ref": "test-001.txt",
    "tipo_documento": "IDENTITY_CARD",
    "campo": "holder_name"
  }'

# Saída esperada:
# {
#   "job_id": "ocr-12345...",
#   "status": "PROCESSANDO",
#   "created_at": "2026-09-10T10:30:00Z"
# }
```

### Teste 2: Verificar Resultado no Banco

```bash
# Listar jobs pendentes
curl -X GET "http://localhost:8211/v1/ocr/review?status=PENDENTE" \
  -H "Authorization: Bearer <seu-token>"
```

**Validação de Segurança:**
- ✅ Resultado **nunca** em plaintext no banco
- ✅ Valor OCR armazenado em `payload_protegido` (AES-256-GCM)
- ✅ Identificação de revisor armazenada como SHA-256
- ✅ Listagens retornam apenas metadados (sem PII)

### Teste 3: Interface Web

Acesse a página de revisão OCR:

```
http://localhost:8083/admin/ocr-review
```

**Esperado:**
- ✅ Status "Pronto" (não bloqueado)
- ✅ Jobs pendentes listar com referência, não com valores OCR
- ✅ Revisor conseguir aprovar/rejeitar resultado

---

## 🔄 Fluxo de Processamento

```
OCR_INPUT_ROOT/document.pdf
    ↓
OcrWorker (Tesseract multipass)
    ↓
Resultado
    ├─→ AUTO (confiança alta)
    │   └─→ Concluído sem fila humana
    │
    └─→ PENDING/REJECTED (baixa confiança ou erro)
        └─→ /admin/ocr-review
            ├─ Revisor aprova → APROVADO (payload protegido)
            ├─ Revisor rejeita → REJEITADO
            └─ Revisor passa → PENDING (fica em fila)
```

---

## 🔐 Segurança — Checklist

Antes de commitar ou publicar:

- [ ] `OCR_DATA_ENCRYPTION_KEY` gerada e validada (32 bytes Base64)
- [ ] Chave **não** commitada em `.env` (verificar `.gitignore`)
- [ ] Diretório `OCR_INPUT_ROOT` acessível e privado (chmod 700 em Unix)
- [ ] Endpoint `/v1/ocr/readiness` retorna `"ready": true`
- [ ] Teste end-to-end com amostra sintética passou
- [ ] Nenhum plaintext de PII em logs ou banco de dados

**⚠️ Em Produção/Staging:**

Mover chave para secret store:

```bash
# Fly.io
flyctl secrets set OCR_DATA_ENCRYPTION_KEY="<chave-base64>" \
  OCR_DATA_KEY_VERSION="v1" \
  OCR_INPUT_ROOT="/data/ocr-input" \
  -a reqsys-api-prod

# Azure Key Vault / Vault corporativo
# Via CLI/API do seu serviço de secrets
```

---

## 📚 Referências

| Recurso | Descrição |
|---------|-----------|
| [`docs/architecture/ocr-secure-review-v2.md`](../architecture/ocr-secure-review-v2.md) | Especificação técnica completa |
| [`docs/architecture/ocr-bounded-context.md`](../architecture/ocr-bounded-context.md) | DDD: domínio e políticas |
| [`backend/app/ocr/storage.py`](../../backend/app/ocr/storage.py) | Implementação de criptografia |
| [`backend/tests/test_ocr_review_api.py`](../../backend/tests/test_ocr_review_api.py) | Testes da API |
| [`scripts/validate-ocr-setup.ps1`](../../scripts/validate-ocr-setup.ps1) | Script de validação |

---

## 🚨 Troubleshooting

| Problema | Causa | Solução |
|----------|-------|--------|
| `OCR_STORE_NOT_READY` ao abrir `/admin/ocr-review` | Chave não configurada | Executar `.\scripts\validate-ocr-setup.ps1` |
| `"key_configured": false` | `OCR_DATA_ENCRYPTION_KEY` inválida ou ausente | Regenerar chave e adicionar a `.env` |
| `"input_root_configured": false` | Diretório não existe ou não acessível | `mkdir -p $OCR_INPUT_ROOT` |
| Backend não responde em `localhost:8211` | Backend não iniciado ou porta em uso | `docker-compose logs backend` ou `lsof -i :8211` |
| Chave com menos de 32 bytes | Geração incompleta ou corrupção | Regenerar com `python -c "..."` |

---

## ✨ Próximos Passos

- [ ] Gerar chave de criptografia
- [ ] Configurar `.env` local
- [ ] Executar `.\scripts\validate-ocr-setup.ps1`
- [ ] Iniciar backend (`docker-compose up` ou `uvicorn`)
- [ ] Validar `/v1/ocr/readiness`
- [ ] Testar com documento sintético
- [ ] Acessar `/admin/ocr-review` e aprovar/rejeitar amostra

**Sucesso:** Status verde em `/v1/ocr/readiness` e `/admin/ocr-review` operacional.
