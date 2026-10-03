# Handoff de pendência externa do P0 — Prospecção Movimento

## Status atual

O código local e o runtime do projeto já foram validados. O que continua pendente é a configuração real do ambiente externo que alimenta o pipeline de e-mail.

## Blocos pendentes

### 1) DSN real do SQL Server

Variável obrigatória:

- `MOVIMENTO_EMAIL_SOURCE_DSN`

Objetivo:

- apontar para o banco/servidor real que alimenta o SSRS legado de Prospecção Movimento
- validar os nomes reais das 4 views/tabelas
- confirmar as colunas esperadas pelo código

### 2) SMTP real para envio

Variáveis obrigatórias:

- `MOVIMENTO_EMAIL_SMTP_HOST`
- `MOVIMENTO_EMAIL_SMTP_PORT`
- `MOVIMENTO_EMAIL_SMTP_USER`
- `MOVIMENTO_EMAIL_SMTP_PASSWORD`
- `MOVIMENTO_EMAIL_SMTP_FROM`
- `MOVIMENTO_EMAIL_RECIPIENTS`

Objetivo:

- validar envio em `dry_run=true`
- validar envio real controlado
- confirmar payload e destinatários

## Conteúdo a preencher

```env
MOVIMENTO_EMAIL_SOURCE_DSN="Driver={ODBC Driver 18 for SQL Server};Server=<SERVIDOR_SQL>;Database=<BANCO>;UID=<USUARIO>;PWD=<SENHA>;Encrypt=yes;TrustServerCertificate=no"
MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS=30

MOVIMENTO_EMAIL_SMTP_HOST="<SMTP_HOST>"
MOVIMENTO_EMAIL_SMTP_PORT=587
MOVIMENTO_EMAIL_SMTP_USER="<SMTP_USER>"
MOVIMENTO_EMAIL_SMTP_PASSWORD="<SMTP_PASSWORD>"
MOVIMENTO_EMAIL_SMTP_USE_TLS=true
MOVIMENTO_EMAIL_SMTP_FROM="<NOME> <EMAIL>"
MOVIMENTO_EMAIL_RECIPIENTS="operacao@empresa.com,ti@empresa.com"
```

## Regras de segurança

- nunca gravar valores reais em código, logs, PRs, issues públicas ou chat compartilhado
- usar cofre/secret manager ou injeção do ambiente de execução
- não expor a senha da connection string ou do SMTP em qualquer artefato textual
- manter a evidência somente em ambiente seguro

## Validação objetiva após preenchimento

```powershell
cd c:\dev\reqsys-v2-enterprise-real
python .\scripts\verificar_movimento_email_fontes.py status
python .\scripts\verificar_movimento_email_fontes.py verificar

cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_movimento_email_api.py -q
```

Se tudo estiver correto, o próximo passo é validar o SMTP com `dry_run=true` e depois o envio real controlado.

## Status executivo

- Local runtime: validado
- Frontend local: validado
- DSN externo: pendente
- SMTP externo: pendente
- Aceite final: bloqueado por ausência de configuração externa real
