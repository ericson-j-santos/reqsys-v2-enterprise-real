# OCR Setup — Checklist de Integração Local

Use este checklist quando estiver preparando seu ambiente OCR para desenvolvimento ou antes de fazer commits que envolvam funcionalidades OCR.

## 📋 Pré-requisitos

- [ ] Python 3.9+ instalado
- [ ] `.env` local criado (copiado de `.env.example`)
- [ ] Acesso ao diretório de entrada OCR configurável

## 🔐 Configuração de Chaves

- [ ] Chave de criptografia gerada com `python -c "import base64,secrets; ..."`
- [ ] Chave com exatamente **32 bytes em Base64** (~43-44 caracteres)
- [ ] `OCR_DATA_ENCRYPTION_KEY` adicionada ao `.env` local
- [ ] `OCR_DATA_KEY_VERSION` configurada como `v1`
- [ ] Nenhuma chave commitada em git (verificar com `git check-ignore .env`)

## 📁 Estrutura de Diretórios

- [ ] Diretório `OCR_INPUT_ROOT` criado (`C:\tmp\ocr-input` ou `/tmp/ocr-input`)
- [ ] Diretório é acessível (teste: `ls -la $OCR_INPUT_ROOT`)
- [ ] Permissões corretas no Unix (`chmod 700`, Windows: NTFS acesso)
- [ ] Espaço em disco disponível (> 1GB recomendado)

## 🧪 Validação Local

- [ ] Script de validação executado: `.\scripts\validate-ocr-setup.ps1`
- [ ] Todos os 4 checks passaram com ✅
- [ ] Variáveis `OCR_*` estão presentes no `.env`
- [ ] Diretório foi criado e é acessível

## 🚀 Teste com Backend

- [ ] Backend iniciado (`docker-compose up` ou `uvicorn`)
- [ ] Porta 8211 respondendo (`curl http://localhost:8211/health`)
- [ ] Endpoint `/v1/ocr/readiness` retorna `"ready": true`
- [ ] JSON de readiness valida:
  ```json
  {
    "encryption": "AES-256-GCM",
    "key_configured": true,
    "input_root_configured": true,
    "plaintext_storage_allowed": false
  }
  ```

## 🧪 Teste End-to-End

- [ ] Documento de teste criado em `OCR_INPUT_ROOT`
- [ ] Job OCR enviado via API (`POST /v1/ocr/jobs`)
- [ ] Resultado processado e armazenado
- [ ] Valor OCR **não** aparece em plaintext no banco
- [ ] Acessar `/admin/ocr-review` sem erros de "STORE_NOT_READY"

## 🔐 Validações de Segurança

- [ ] Nenhuma chave em logs de console
- [ ] `.env` está em `.gitignore` (validar com `git check-ignore .env`)
- [ ] Variáveis não foram expostas em commits anteriores (verificar git history)
- [ ] Em produção/staging: chave será armazenada em secret store, não em `.env`

## 📝 Documentação

- [ ] Leitura de [`docs/guides/ocr-setup-local-development.md`](../docs/guides/ocr-setup-local-development.md)
- [ ] Referência a [`docs/architecture/ocr-secure-review-v2.md`](../docs/architecture/ocr-secure-review-v2.md) para detalhes técnicos
- [ ] Entendimento do fluxo: input → worker → criptografia → revisão humana

## 🎯 Pronto para Commit?

- [ ] Nenhuma chave de criptografia nos arquivos
- [ ] Documentação atualizada se houve mudanças no fluxo
- [ ] Testes locais passaram (validação + E2E)
- [ ] Branch está sincronizado com `main`

---

## 🆘 Troubleshooting Rápido

| Problema | Diagnóstico | Solução |
|----------|-------------|--------|
| `OCR_STORE_NOT_READY` | Endpoint `/v1/ocr/readiness` retorna erro | Executar `.\scripts\validate-ocr-setup.ps1` |
| `key_configured: false` | `OCR_DATA_ENCRYPTION_KEY` não em `.env` | Gerar chave e adicionar ao `.env` |
| `input_root_configured: false` | Diretório não existe | `mkdir -p $OCR_INPUT_ROOT` |
| Backend não inicia | Porta 8211 em uso | `lsof -i :8211` (Linux) ou `netstat -ano \| grep 8211` (Windows) |
| Chave inválida | Base64 corrupto ou tamanho errado | Regenerar com script Python |

---

**Data de criação:** 2026-09-10  
**Versão:** OCR v2 (AES-256-GCM)  
**Responsável por atualizar:** Time OCR + @ericson-j-santos
