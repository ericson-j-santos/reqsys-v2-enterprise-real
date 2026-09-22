# ADR-022 — Autonomous Operations Platform P0.1

## Status

Proposto / em validação por PR.

## Contexto

O ReqSys está evoluindo para maturidade enterprise, mas a operação autônoma ainda não pode ser declarada como avançada sem evidência real de implementação, testes, auditoria e validação operacional.

O desvio corrigido neste incremento é separar explicitamente:

| Conceito | Regra |
|---|---|
| Estado atual evidenciado | Somente aquilo que existe no código e nos testes |
| Estado alvo | Meta estratégica |
| Projeção | Resultado esperado após validação completa |
| Maturidade avançada | Só pode ser declarada após implementação e evidência |

## Decisão

Implementar a primeira fatia da **Autonomous Operations Platform (AOP) P0.1** com foco em:

1. motor de maturidade operacional;
2. snapshot consolidado de operação autônoma;
3. políticas governadas de auto-remediação;
4. bloqueio explícito de ações destrutivas sem health validator e auditoria;
5. endpoint operacional para consumo pelo OCC e futuras telas analíticas.

## Escopo implementado

| Item | Status |
|---|---|
| `backend/app/core/autonomous_operations.py` | Implementado |
| Endpoint `/operacao-autonoma/maturidade` | Implementado |
| Testes de contrato e governança | Implementado |
| Separação atual x alvo | Implementado |
| Auto-remediação destrutiva real | Bloqueada por política |

## Decisão de segurança

Ações autônomas destrutivas, como restart controlado, rollback real, failover ou alteração de runtime, permanecem bloqueadas até existir:

- health validator por componente;
- auditoria persistente;
- limite de execução;
- política de rollback;
- trilha de decisão rastreável por `correlation_id`.

## Consequências

### Positivas

| Benefício | Impacto |
|---|---|
| Maturidade passa a ser calculada com evidência | Reduz falso status avançado |
| Operação autônoma ganha contrato de API | Permite dashboard e analytics |
| Segurança governa auto-remediação | Reduz risco operacional |
| Gaps viram backlog explícito | Melhora rastreabilidade |

### Limitações conhecidas

| Limitação | Próximo incremento |
|---|---|
| Score ainda baseado em baseline estático | Persistir métricas reais por execução |
| Sem executor real de remediação | Implementar executor governado |
| Sem health validator por componente | Implementar Runtime Health Validator |
| Sem dashboard dedicado | Implementar tela analítica no frontend |

## Critérios para elevar maturidade

| Pilar | Condição mínima |
|---|---|
| Operação Autônoma | Executor governado + auditoria + validação |
| Observabilidade | Métricas, logs e traces correlacionados |
| Segurança | Policy-as-Code + bloqueios reais de ambiente |
| CI/CD | CI verde recorrente com quality gates |
| Runtime Intelligence | Health por componente + anomalias |

## Próximo incremento recomendado

**AOP P0.2 — Runtime Health Validator + Executor Governado de Remediação**.

Objetivo: permitir que algumas ações saiam de `bloqueado_por_politica` para `apto_auto_remediacao`, sem comprometer segurança ou rastreabilidade.
