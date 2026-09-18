# ADR-023 — AOP P0.2 Runtime Health Validator e Executor Governado

## Status

Proposto / em validação no PR #75.

## Contexto

O incremento AOP P0.1 criou a base de maturidade, políticas e ações classificadas. Porém, operação autônoma real exige uma camada adicional para avaliar saúde de runtime e decidir se uma remediação pode ou não ser executada.

Sem essa camada, qualquer tentativa de auto-remediação destrutiva, como restart ou rollback, poderia mascarar causa raiz, aumentar impacto ou violar governança.

## Decisão

Implementar o **AOP P0.2** com:

| Componente | Decisão |
|---|---|
| Runtime Health Validator | Implementado como snapshot versionado por componente |
| Executor Governado | Implementado para avaliar remediações com política default deny |
| Ações não destrutivas | Permitidas em dry-run ou execução governada |
| Ações destrutivas | Bloqueadas até existir auditoria persistente e rollback validado |
| Endpoints | Expostos em `/operacao-autonoma/runtime-health` e `/operacao-autonoma/remediacoes/avaliar` |

## Endpoints

```http
GET /operacao-autonoma/runtime-health
POST /operacao-autonoma/remediacoes/avaliar
```

## Regras de segurança

| Regra | Estado |
|---|---|
| Default deny | Ativo |
| Componente desconhecido | Bloqueado |
| Restart real | Bloqueado |
| Rollback real | Bloqueado |
| Retry governado | Permitido com limite e auditoria |
| Bloqueio de deploy | Permitido como ação não destrutiva |
| Dry-run | Preferencial para validação inicial |

## Consequências

### Benefícios

| Benefício | Impacto |
|---|---|
| Operação autônoma ganha validador por componente | Reduz decisão cega |
| Executor diferencia ação destrutiva e não destrutiva | Reduz risco operacional |
| Contratos de API testáveis | Melhora CI/CD e governança |
| Ações críticas continuam bloqueadas | Preserva segurança |

### Limitações

| Limitação | Próximo passo |
|---|---|
| Health ainda usa baseline interno | Conectar métricas reais |
| Auditoria ainda retornada no payload | Persistir em storage durável |
| Sem executor de infraestrutura real | Implementar adapters por ambiente |
| Sem dashboard dedicado | Criar tela operacional navegável |

## Próximo incremento recomendado

**AOP P0.3 — Auditoria Persistente de Incidentes e Remediações**.

Objetivo: transformar decisões retornadas em eventos persistidos e rastreáveis para permitir avanço seguro do score de operação autônoma.
