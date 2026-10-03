# Product Intelligence Event Model

## Objetivo

Iniciar a camada `ReqSys Product Intelligence Layer`, saindo do eixo operacional/CI-CD e entrando na inteligência funcional do produto ReqSys.

Este modelo padroniza eventos funcionais relacionados a requisitos, refinamentos, critérios BDD, riscos, decisões e rastreabilidade.

## Escopo

- Eventos de requisitos.
- Eventos de refinamento.
- Eventos de critérios BDD.
- Eventos de riscos.
- Eventos de decisão.
- Eventos de rastreabilidade.
- Eventos de qualidade funcional.
- Base para analytics funcionais.
- Base para IA aplicada ao ReqSys.

## Fora de escopo

- Alteração de runtime produtivo.
- Execução automática de agentes.
- Integração com bases corporativas reais.
- Escrita automática em sistemas externos.
- Mudança em gates de CI/CD.

## Modelo canônico de evento

```json
{
  "schema_version": "1.0.0",
  "event_id": "uuid",
  "event_type": "requirement.created",
  "event_class": "PRODUCT_INTELLIGENCE",
  "occurred_at": "2026-06-24T00:00:00Z",
  "source": {
    "system": "reqsys",
    "channel": "ui|api|agent|import|workflow",
    "actor_type": "user|agent|system",
    "actor_id": "string"
  },
  "requirement": {
    "id": "string",
    "title": "string",
    "type": "functional|non_functional|business_rule|constraint",
    "status": "draft|refined|approved|implemented|tested|validated",
    "priority": "must|should|could|wont",
    "confidence": "low|medium|high"
  },
  "quality": {
    "bdd_coverage": 0,
    "ambiguity_score": 0,
    "traceability_score": 0,
    "risk_score": 0,
    "readiness_score": 0
  },
  "traceability": {
    "parent_ids": [],
    "linked_prs": [],
    "linked_tests": [],
    "linked_decisions": [],
    "linked_risks": []
  },
  "governance": {
    "correlation_id": "uuid",
    "pii_masked": true,
    "human_review_required": true,
    "ai_generated": false,
    "evidence_level": "none|partial|complete"
  }
}
```

## Tipos iniciais de evento

| Evento | Objetivo |
|---|---|
| `requirement.created` | Requisito criado |
| `requirement.refined` | Requisito refinado |
| `requirement.approved` | Requisito aprovado |
| `requirement.rejected` | Requisito rejeitado |
| `bdd.generated` | Critérios BDD gerados |
| `risk.identified` | Risco funcional identificado |
| `traceability.linked` | Rastreabilidade criada |
| `decision.recorded` | Decisão funcional registrada |
| `quality.scored` | Score funcional calculado |
| `gap.detected` | Lacuna funcional detectada |

## Métricas funcionais iniciais

| Métrica | Descrição |
|---|---|
| `bdd_coverage` | Cobertura de critérios BDD |
| `ambiguity_score` | Grau de ambiguidade |
| `traceability_score` | Qualidade da rastreabilidade |
| `risk_score` | Exposição funcional a risco |
| `readiness_score` | Prontidão para implementação/teste |

## Uso previsto

Este modelo será usado para alimentar:

- dashboards funcionais;
- analytics de requisitos;
- IA de refinamento;
- rastreabilidade viva;
- qualidade funcional;
- recomendação de próximos passos;
- explicabilidade de decisões;
- ReqSys Product Intelligence Layer.

## Próximos incrementos

1. Product Intelligence Event Validator.
2. Requirement Quality Scoring Engine.
3. Functional Traceability Graph.
4. ReqSys Product Intelligence Dashboard.
5. AI-assisted Product Decision Intelligence.
