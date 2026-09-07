# Prospecção Movimento — descoberta SQL e envio Microsoft Graph

## Objetivo

Reduzir as duas pendências externas do P0 ao mínimo inevitável:

1. o ReqSys descobre servidor, banco e objetos SQL a partir das definições SSRS exportadas; o DBA apenas cria/autoriza a identidade técnica;
2. o ReqSys envia pelo Microsoft Graph usando a identidade Entra já existente; o administrador apenas concede `Mail.Send` de aplicação e autoriza a caixa remetente.

## 1. Descoberta da origem SQL Server

### Entrada

Exportar do SSRS o relatório de Prospecção Movimento e, se houver, os Data Sources compartilhados (`.rdl`/`.rds`). Não publicar esses arquivos em issue ou PR quando contiverem dados internos.

### Execução

```powershell
python scripts/descobrir_movimento_email_origem_ssrs.py C:\evidencias\ssrs\movimento \
  --output artifacts/movimento-email/ssrs-discovery.json
```

Ou configure apenas o caminho local:

```text
MOVIMENTO_EMAIL_SSRS_EXPORT_PATH=C:\evidencias\ssrs\movimento
```

O resultado contém somente:

- servidor(es) identificados;
- banco(s) identificados;
- objetos SQL candidatos obtidos de `FROM`, `JOIN`, `UPDATE`, `INTO` e `EXEC`;
- referências a Data Sources compartilhados ainda não exportados;
- molde de DSN sem usuário e sem senha.

Mesmo que o RDL contenha `UID`, `User ID`, `PWD` ou `Password`, os valores não são retornados.

### Saída esperada

```text
Driver={ODBC Driver 18 for SQL Server};Server=<DESCOBERTO>;Database=<DESCOBERTO>;Encrypt=yes;TrustServerCertificate=no;Authentication=<DEFINIR_COM_DBA>
```

### Ação restante do DBA

1. validar servidor/banco/objetos descobertos;
2. criar ou selecionar identidade técnica de menor privilégio;
3. conceder somente leitura/execução necessária;
4. armazenar a credencial em cofre seguro;
5. injetar `MOVIMENTO_EMAIL_SOURCE_DSN` no runtime;
6. executar `python scripts/verificar_movimento_email_fontes.py verificar`.

## 2. Envio por Microsoft Graph

O SMTP continua disponível como compatibilidade. Para usar Graph:

```text
MOVIMENTO_EMAIL_PROVIDER=graph
MOVIMENTO_EMAIL_GRAPH_SENDER=reqsys@empresa.com
```

O Graph reutiliza:

```text
AZURE_TENANT_ID
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
```

Nenhuma senha SMTP é necessária.

### Permissão administrativa

No Microsoft Entra ID, conceder à aplicação usada pelo ReqSys:

- Microsoft Graph;
- Application permission;
- `Mail.Send`;
- consentimento administrativo.

Como `Mail.Send` de aplicação pode enviar como usuários da organização, restringir a aplicação à caixa técnica `MOVIMENTO_EMAIL_GRAPH_SENDER` usando o mecanismo corporativo de escopo de acesso de aplicações do Exchange/Entra aplicável ao tenant.

### Validação

1. `POST /v1/movimento-email/fila/consumir` com `{"dry_run": true}` — não chama Graph;
2. enfileirar uma mensagem de teste para destinatário autorizado;
3. executar `POST /v1/movimento-email/fila/consumir` com `{"dry_run": false}`;
4. exigir HTTP 202 do Graph internamente e estado `SENT` na fila;
5. validar `X-Correlation-ID` no MIME/evidência;
6. confirmar recebimento e item enviado da caixa técnica.

## Segurança

- nunca gravar `AZURE_CLIENT_SECRET`, DSN real ou credenciais em issue/PR/log;
- o adaptador Graph não registra access token nem corpo bruto de respostas de erro;
- erros 4xx são tratados como rejeição não transitória; 408/429/5xx usam retentativa e circuit breaker;
- SMTP não foi removido para evitar regressão, mas Graph é o alvo recomendado para o ambiente Microsoft 365.
