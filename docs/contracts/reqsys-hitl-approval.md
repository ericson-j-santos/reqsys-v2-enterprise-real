# ReqSys HITL Approval Orchestrator

## Objetivo

Automatizar a solicitação, notificação e captura de decisões humanas sem atribuir aprovação a bots. O GitHub é a fonte auditável; Teams e e-mail são canais de entrega.

## Criação da solicitação

O workflow `ReqSys HITL Approval Orchestrator` pode ser iniciado por `workflow_dispatch` com:

- título;
- controle/escopo;
- resumo;
- URL GitHub das evidências;
- prazo opcional.

A execução cria uma issue com o marcador `<!-- reqsys-hitl-approval -->` e o label `hitl-approval-request`.

## Notificações

### Teams

O workflow usa `scripts/notify_hitl_approval_teams.py` e o Teams Messaging Gateway existente.

Configuração opcional:

- `TEAMS_GATEWAY_DESTINO_ID`;
- `TEAMS_GATEWAY_BASE_URL`.

A mensagem contém links clicáveis para abrir a solicitação e instruções para aprovar, rejeitar ou solicitar ajuste.

### E-mail

O workflow sempre gera um arquivo MIME `.eml` auditável. O envio SMTP ocorre somente quando estes secrets existem:

- `HITL_EMAIL_FROM`;
- `HITL_EMAIL_TO`;
- `HITL_SMTP_HOST`;
- `HITL_SMTP_PORT`;
- `HITL_SMTP_USERNAME`;
- `HITL_SMTP_PASSWORD`;
- `HITL_SMTP_MODE` (`plain`, `starttls` ou `ssl`).

Credenciais nunca são gravadas em artifacts ou logs.

## Decisão autenticada

A decisão é registrada em comentário na issue:

```text
/approve Evidências revisadas e risco residual aceito.
/reject Evidência insuficiente para assumir responsabilidade formal.
/adjust Incluir assinatura jurídica e evidência real do IdP.
```

Regras:

- justificativa mínima de 10 caracteres;
- ator não pode terminar com `[bot]`;
- permissão GitHub deve ser `write`, `maintain` ou `admin`;
- issue deve possuir `hitl-approval-request`;
- o comentário e a issue formam referências imutáveis.

## Saída

Artifact `reqsys-hitl-decision-<issue>` retido por 365 dias contendo:

- ator e permissão;
- decisão e justificativa;
- data;
- issue e comentário;
- SHA da origem;
- SHA-256 da solicitação;
- SHA-256 da decisão;
- correlation ID;
- próxima ação permitida;
- `production_touched=false`.

## Efeitos

| Decisão | Estado da issue | Ação automática |
|---|---|---|
| `approve` | fecha com `hitl-approved` | reexecuta somente gates seguros |
| `reject` | fecha com `hitl-rejected` | mantém entrega bloqueada |
| `adjust` | mantém aberta com `hitl-adjustment-requested` | aguarda nova evidência |

A aprovação não altera diretamente a matriz BACEN, não executa deploy e não libera PROD. Mudanças de política ou status continuam exigindo PR específica vinculada ao artifact da decisão.
