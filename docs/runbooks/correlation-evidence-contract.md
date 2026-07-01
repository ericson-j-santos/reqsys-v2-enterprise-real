# Contrato de Evidência por Correlation ID

> Atualização: 2026-06-30 13:30 BRT  
> Escopo: contrato documental para rastreabilidade operacional.

## Objetivo

Definir um contrato mínimo para evidências operacionais correlacionáveis entre PR, CI, runtime, logs, dashboard e runbooks, sem exigir mudança imediata no código da aplicação.

## Identificador canônico

Todo fluxo operacional relevante deve transportar um `correlation_id` único, estável durante a transação e seguro para exposição em logs técnicos.

Formato recomendado:

```text
reqsys-<dominio>-<yyyyMMddHHmmss>-<sufixo_curto>
```

Exemplo:

```text
reqsys-ci-20260630133000-a7f3
```

## Campos mínimos

| Campo | Obrigatório | Descrição |
| --- | --- | --- |
| `correlation_id` | Sim | Identificador rastreável ponta a ponta. |
| `source` | Sim | Origem da evidência: PR, CI, runtime, dashboard ou agente. |
| `environment` | Sim | `dev`, `test`, `staging`, `prod` ou `local`. |
| `status` | Sim | `success`, `warning`, `failed`, `blocked` ou `unknown`. |
| `timestamp` | Sim | Data/hora em ISO 8601. |
| `evidence_ref` | Não | Referência para PR, Action, artifact ou dashboard sem expor segredo. |
| `risk_level` | Sim | `low`, `medium`, `high` ou `critical`. |
| `rollback` | Não | Estratégia de reversão quando aplicável. |

## Regras de segurança

- Não incluir PII, secrets, tokens, cookies ou payloads sensíveis.
- Mascarar identificadores pessoais quando indispensáveis.
- Preferir referências controladas para artifacts em vez de colar conteúdo sensível.
- Preservar o mesmo `correlation_id` em logs, dashboards e relatórios derivados.

## Exemplo JSON

```json
{
  "correlation_id": "reqsys-ci-20260630133000-a7f3",
  "source": "github_actions",
  "environment": "staging",
  "status": "success",
  "timestamp": "2026-06-30T13:30:00-03:00",
  "evidence_ref": "github_actions_run",
  "risk_level": "low",
  "rollback": "revert_pr"
}
```

## Rollback

Remover este documento. Não há alteração em runtime, logs, dashboards ou CI.
