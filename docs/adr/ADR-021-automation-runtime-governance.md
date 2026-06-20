# ADR-021 — Automation Runtime Governance

## Status

Proposto.

## Contexto

O ReqSys possui automações críticas para relatórios executivos, monitoramento de PRs, CI/CD, conectores e governança operacional. Uma automação não deve ser considerada operacional apenas por estar cadastrada ou habilitada.

Foi identificado o risco de falso positivo operacional quando uma tarefa está ativa, mas sem evidência de execução, entrega ou confirmação pós-envio.

## Decisão

Adotar `Automation Runtime Governance` como padrão obrigatório para automações críticas do ReqSys.

Toda automação crítica deve registrar e validar:

- identificador técnico e funcional;
- `correlation_id` por execução;
- início e fim da execução;
- status normalizado;
- geração do relatório ou artefato;
- entrega no canal configurado;
- confirmação pós-entrega quando aplicável;
- retry/backoff com limite controlado;
- falhas estruturadas;
- evidência persistida;
- exposição no `/monitoramento-operacional`.

## Estados canônicos

| Estado | Significado |
|---|---|
| `scheduled` | Agendamento existe. |
| `enabled` | Agendamento está ativo. |
| `running` | Execução em andamento. |
| `generated` | Artefato ou relatório gerado. |
| `delivery_requested` | Envio solicitado ao canal. |
| `delivered` | Canal confirmou envio. |
| `delivery_confirmed` | Evidência pós-entrega confirmada. |
| `retrying` | Retry em andamento. |
| `failed` | Execução falhou. |
| `blocked` | Pré-condição obrigatória ausente. |
| `unknown` | Estado não comprovado. |

## Regras obrigatórias

- `enabled=true` não significa entrega concluída.
- `last_run_time` vazio torna a execução não comprovada.
- Toda falha deve registrar causa, impacto, tentativa de retry e próxima ação.
- Produção não deve assumir sucesso sem evidência.
- Todo relatório deve fechar com resumo executivo: feito, estado atual, riscos, pendências e próxima ação.

## Modelo mínimo de evidência

```json
{
  "automation_id": "reqsys-executive-report",
  "correlation_id": "uuid",
  "execution_started_at": "datetime",
  "execution_finished_at": "datetime",
  "status": "delivery_confirmed",
  "report_generated": true,
  "delivery_channel": "mail",
  "recipients_ref": "configured_recipients",
  "sent_message_ref": "provider_message_id",
  "delivery_confirmed": true,
  "retry_count": 0,
  "evidence_uri": "docs/evidencias-operacionais/..."
}
```

## Integração obrigatória

O módulo `/monitoramento-operacional/automacoes` deve expor:

- automação;
- frequência;
- próxima execução;
- última execução;
- duração;
- status;
- canal;
- confirmação de entrega;
- retries;
- falhas;
- `correlation_id`;
- evidência;
- recomendação executiva.

## Consequências

### Positivas

- Reduz falso positivo operacional.
- Melhora auditoria.
- Padroniza relatórios executivos.
- Fortalece observabilidade.
- Integra automações, CI/CD, conectores e evidências.

### Custos

- Exige persistência de evidências.
- Exige validação pós-entrega.
- Exige instrumentação adicional.

## Critérios de aceite

- ADR publicado.
- Runbook publicado.
- Checklist publicado.
- Modelo de evidência publicado.
- PR mantido em draft até CI verde e revisão.
