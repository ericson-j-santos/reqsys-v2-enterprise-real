# Plano de execução para pendências externas do P0

## Objetivo

Fechar os blocos reais do pipeline Prospecção Movimento/Portabilidade Consignado que dependem de ambiente externo e não de correção de código local:

1. `MOVIMENTO_EMAIL_SOURCE_DSN` real do SQL Server
2. `MOVIMENTO_EMAIL_SMTP_*` reais para envio de e-mail

## Critério de aceitação do P0

O P0 só é fechado quando houver evidência real de:

- conexão real ao SQL Server corporativo
- contrato dos 4 datasets validado contra o schema real
- execução real de `jobs/executar` com dados reais
- envio real do SMTP validado em ambiente de teste
- readiness operacional e evidência de promoção registrados

## Escopo fora do P0

Os itens já validados localmente não entram mais neste plano:

- backend API e testes do pipeline
- frontend build e testes unitários
- runtime smoke local
- browser real local

## Ordem operacional

### Fase 1 — Obter e validar a origem real do SQL Server

#### 1.1 Preparar credenciais

Obter do time de dados/infra:

- `MOVIMENTO_EMAIL_SOURCE_DSN`
- nomes reais das 4 views/tabelas do SSRS legado
- ambiente correto (teste ou produção controlada)

#### 1.2 Registrar no ambiente

Adicionar no `.env` ou no cofre operacional, sem gravar valor em logs/PRs:

```env
MOVIMENTO_EMAIL_SOURCE_DSN="Driver={ODBC Driver 18 for SQL Server};Server=...;Database=...;UID=...;PWD=...;Encrypt=yes"
MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS=30
```

#### 1.3 Validar conexão e nomes reais

Executar na raiz do repo:

```powershell
cd c:\dev\reqsys-v2-enterprise-real
.\backend\.venv\Scripts\python.exe .\scripts\verificar_movimento_email_fontes.py status
.\backend\.venv\Scripts\python.exe .\scripts\verificar_movimento_email_fontes.py verificar
```

#### 1.4 Ajustar os scripts SQL de origem

Se os nomes reais divergirem dos nomes assumidos, ajustar:

- `backend/app/services/movimento_email/sql/views/V1__vw_prospeccao_movimento_fechamento_diario.sql`
- `backend/app/services/movimento_email/sql/views/V1__vw_prospeccao_movimento_pendencias_cadastro.sql`
- `backend/app/services/movimento_email/sql/views/V1__vw_prospeccao_movimento_pendencias_historicas.sql`
- `backend/app/services/movimento_email/sql/views/V1__vw_prospeccao_movimento_pendencias_observacao.sql`

Regra: não mexer no versionamento sem abrir nova versão (`V2__...`), conforme o README das views.

#### 1.5 Validar o contrato ao vivo

Executar em backend com ambiente configurado:

```powershell
cd c:\dev\reqsys-v2-enterprise-real\backend
.\.venv\Scripts\python.exe -m pytest tests/test_movimento_email_api.py -q
```

Marcar como concluído apenas se a origem real estiver acessível e a rotina aceitar dados reais sem cair em placeholder.

---

### Fase 2 — Validar envio real pelo SMTP

#### 2.1 Obter credenciais reais

Solicitar do time responsável:

- `MOVIMENTO_EMAIL_SMTP_HOST`
- `MOVIMENTO_EMAIL_SMTP_PORT`
- `MOVIMENTO_EMAIL_SMTP_USER`
- `MOVIMENTO_EMAIL_SMTP_PASSWORD`
- `MOVIMENTO_EMAIL_SMTP_FROM`
- `MOVIMENTO_EMAIL_SMTP_USE_TLS`
- `MOVIMENTO_EMAIL_RECIPIENTS` ou destinatários de teste

#### 2.2 Configurar e testar sem envio real

```env
MOVIMENTO_EMAIL_SMTP_HOST=smtp.exemplo
MOVIMENTO_EMAIL_SMTP_PORT=587
MOVIMENTO_EMAIL_SMTP_USER=usuario
MOVIMENTO_EMAIL_SMTP_PASSWORD=***
MOVIMENTO_EMAIL_SMTP_FROM="ReqSys <noreply@exemplo.com>"
MOVIMENTO_EMAIL_SMTP_USE_TLS=true
MOVIMENTO_EMAIL_RECIPIENTS="teste@exemplo.com"
```

Validar primeiro com `dry_run=true` no endpoint:

```http
POST /v1/movimento-email/fila/consumir
{
  "dry_run": true,
  "lote_max": 10
}
```

#### 2.3 Teste real controlado

Quando a origem e o SMTP estiverem válidos, rodar:

```http
POST /v1/movimento-email/jobs/executar
{
  "data_referencia": "2026-09-07",
  "destinatarios": ["teste@exemplo.com"]
}
```

Em seguida:

```http
POST /v1/movimento-email/fila/consumir
{
  "dry_run": false,
  "lote_max": 10
}
```

#### 2.4 Evidência de envio

Armazenar evidência de:

- resposta HTTP do endpoint
- quantidade de itens enviados
- remetente/assunto/recipientes
- e-mail recebido em caixa de teste ou ambiente controlado
- logs e correlation_id

---

### Fase 3 — Gates finais de promoção e operação

#### 3.1 Verificar readiness operacional

Executar:

```powershell
cd c:\dev\reqsys-v2-enterprise-real
.\backend\.venv\Scripts\python.exe .\scripts\validate_public_runtime.py --base-url https://reqsys-api-dev.fly.dev --environment dev --output .\artifacts\public-runtime-dev.json --readiness-output .\artifacts\public-readiness-dev.json
```

#### 3.2 Registrar evidência de promoção

- artifact do contrato real
- artifact de runtime readiness
- artifact de e-mail enviado
- aprovação humana e review de secrets

#### 3.3 Fechar o P0

Só fechar após:

- DSN real validado
- SMTP real validado
- payload real validado
- readiness operacional verde
- evidência escrita e arquivada

## Risco e proteção

- Nunca concluir P0 com somente mock, stub ou teste unitário.
- Não usar `dry_run` como substituto de envio real.
- Não registrar segredos no repo, logs, artefatos públicos ou PR.
- Separar sempre em relatório: qualidade técnica, publicação real e aceite de negócio.

## Checklist de acompanhamento

- [ ] Obter `MOVIMENTO_EMAIL_SOURCE_DSN`
- [ ] Validar conexão real ao SQL Server
- [ ] Confirmar nomes reais das 4 views
- [ ] Ajustar SQL de origem
- [ ] Validar contrato real
- [ ] Obter `MOVIMENTO_EMAIL_SMTP_*`
- [ ] Validar `dry_run=true`
- [ ] Validar envio real controlado
- [ ] Registrar evidência de e-mail enviado
- [ ] Confirmar readiness operacional
- [ ] Finalizar P0 com evidência completa
