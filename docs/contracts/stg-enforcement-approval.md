# STG Enforcement Approval

## Objetivo

Registrar uma decisão humana, auditável e vinculada ao histórico real do gate de promoção antes de qualquer alteração do STG de `warning-only` para `blocking`.

## Pré-condição

O artifact `environment-promotion-history/history.json` deve informar:

```json
{"stg_maturity": {"status": "ready_for_human_approval"}}
```

Uma solicitação `approve` sem essa evidência produz `blocked_by_evidence`.

## Entradas obrigatórias

- decisão: `approve` ou `reject`;
- justificativa;
- ticket ou change record;
- run ID imutável do histórico;
- ator autenticado pelo GitHub;
- SHA avaliado.

## Saída

Artifact `stg-enforcement-approval/approval.json`, retido por 365 dias, contendo:

- `correlation_id` determinístico;
- decisão solicitada e decisão efetiva;
- aprovador, justificativa e ticket;
- origem da evidência;
- contadores da janela STG;
- próxima ação permitida.

## Estados

| Estado | Condição | Próxima ação |
|---|---|---|
| `approved_for_policy_change` | aprovação humana e maturidade válida | abrir PR específico de política |
| `blocked_by_evidence` | aprovação solicitada sem maturidade | manter `warning-only` e coletar evidência |
| `rejected` | rejeição humana | manter `warning-only` |

## Guardrails

- o workflow não altera branch protection;
- o workflow não altera o gate de promoção;
- o workflow não executa deploy;
- a aprovação não é válida sem artifact histórico específico;
- o ambiente GitHub `stg-governance` pode exigir revisores protegidos;
- a mudança para modo bloqueante deve ocorrer em PR separado e referenciar o artifact de aprovação.

## Sequência governada

1. Gate de promoção gera decisões STG.
2. Histórico acumula cinco execuções válidas.
3. Maturidade retorna `ready_for_human_approval`.
4. Responsável executa `STG Enforcement Approval`.
5. Workflow publica a decisão auditável.
6. Somente então um PR separado pode alterar STG para `blocking`.
