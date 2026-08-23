# STG Enforcement Approval

## Objetivo

Registrar uma decisão humana, auditável e vinculada ao histórico real do gate de promoção antes de qualquer alteração protegida da política bloqueante do STG.

## Pré-condição

O artifact `environment-promotion-history/history.json` deve informar:

```json
{
  "contract": "reqsys-environment-promotion-history",
  "stg_enforcement_maturity": {
    "status": "ready_for_human_approval",
    "automatic_change_allowed": false,
    "required_window": 5,
    "observed_window": 5,
    "criteria_met": true
  }
}
```

Uma solicitação `approve` sem essa evidência produz `blocked_by_evidence`.

## Entradas obrigatórias

- decisão: `approve` ou `reject`;
- número do PR de política aberto;
- justificativa;
- ticket ou change record;
- run ID imutável do histórico;
- ator autenticado pelo GitHub, com `sender.type=User`;
- SHA exato da cabeça do PR, resolvido pelo próprio workflow.

## Saída

Artifact `stg-enforcement-approval/approval.json`, retido por 365 dias, contendo:

- `correlation_id` determinístico;
- modo obrigatório `human_workflow_dispatch`;
- decisão solicitada e decisão efetiva;
- aprovador, justificativa e ticket;
- número do PR, SHA e run ID da evidência;
- contadores da janela STG;
- próxima ação permitida.

## Estados

| Estado | Condição | Próxima ação |
|---|---|---|
| `approved_for_policy_change` | aprovação humana e maturidade válida | autorizar o PR e SHA vinculados |
| `blocked_by_evidence` | aprovação solicitada sem maturidade | preservar a política atual e coletar evidência |
| `rejected` | rejeição humana | preservar a política atual |

## Guardrails

- o workflow não altera branch protection;
- o workflow não altera o gate de promoção;
- o workflow não executa deploy;
- a aprovação não é válida sem artifact histórico específico;
- apenas `workflow_dispatch` iniciado por ator humano pode produzir aprovação efetiva;
- identidades terminadas em `[bot]`, dispatch encadeado e tickets temporários automatizados são rejeitados;
- a autorização falha fechada sem artifact válido para o número e o SHA atuais do PR;
- não existe exceção temporária ou fallback sintético;
- o ambiente GitHub `stg-governance` pode exigir revisores protegidos;
- a mudança para modo bloqueante deve ocorrer em PR separado e referenciar o artifact de aprovação.

## Sequência governada

1. Gate de promoção gera decisões STG.
2. Histórico acumula cinco execuções válidas.
3. Maturidade retorna `ready_for_human_approval`.
4. Responsável humano executa manualmente `STG Enforcement Approval` para o PR aberto.
5. Workflow publica a decisão auditável.
6. Somente então o PR protegido de política STG pode ser autorizado.
