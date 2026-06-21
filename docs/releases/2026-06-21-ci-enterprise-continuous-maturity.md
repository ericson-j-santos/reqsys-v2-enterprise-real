# Release Note — 2026-06-21 — CI Enterprise Continuous Maturity

## Resumo

Incremento para estabilizar a esteira do ReqSys e reduzir falhas recorrentes de CI por meio de pipeline em camadas, guardrails determinísticos, regressão agendada e observabilidade operacional.

## Escopo implementado

| Item | Status | Evidência |
|---|---|---|
| Branch dedicada | Implementado | `ci/enterprise-continuous-maturity` |
| Guardrails determinísticos | Implementado | `scripts/ci_enterprise_guardrails.py` |
| CI fast bloqueante | Implementado | `.github/workflows/ci-enterprise-fast.yml` |
| Regressão enterprise | Implementado | `.github/workflows/ci-enterprise-regression.yml` |
| Observabilidade de CI | Implementado | `.github/workflows/ci-enterprise-observability.yml` |
| ADR | Implementado | `docs/adr/ADR-2026-06-21-ci-enterprise-continuous-maturity.md` |
| Runbook/documentação viva | Implementado | `docs/governanca/CI_ENTERPRISE_CONTINUOUS_MATURITY.md` |
| Correção objetiva de falso positivo | Implementado | `scripts/ci_enterprise_guardrails.py` |

## Decisões aplicadas

1. Separação entre CI rápido e regressão completa.
2. Cancelamento automático de execuções redundantes por branch/ref.
3. Versões fixas de Node e Python.
4. Relatórios publicados como artifacts.
5. Guardrails para bloquear insegurança e não determinismo.
6. Política explícita para flaky tests.
7. Estado de maturidade condicionado à evidência real, não a status manual.
8. Guardrails de segurança passam a bloquear apenas código runtime/config produtivo; testes, specs, fixtures, mocks, exemplos e documentação não bloqueiam CI por falso positivo.

## Impacto esperado

| Indicador | Antes | Meta após estabilização |
|---|---|---|
| Tempo até feedback inicial | Alto/variável | <= 8 min no fast path |
| Regressão intermitente | Frequente | Redução progressiva |
| Rerun sem causa raiz | Comum | Exceção documentada |
| Falha recorrente | Corrigida pontualmente | Convertida em guardrail/teste |
| Evidência operacional | Dispersa | Artifact + summary por workflow |
| Falso positivo de guardrail | Bloqueante | Reduzido por classificação de contexto |

## Correção objetiva aplicada

| Ajuste | Resultado |
|---|---|
| Ignorar `tests`, `__tests__`, `.spec`, `.test`, fixtures e mocks | Evita bloqueio de CI por dados controlados de teste |
| Tratar documentação como warning | Mantém visibilidade sem bloquear merge indevidamente |
| Manter erro em runtime/config produtivo | Preserva segurança real |
| Classificar exemplos e `.env.example` como não bloqueantes | Evita falso positivo em material de orientação |

## Pendências intencionais

| Pendência | Motivo |
|---|---|
| Branch protection obrigatória | Configuração do repositório precisa ser ajustada na interface/admin API conforme política vigente |
| Métricas históricas reais | Dependem das próximas execuções dos workflows |
| Elevação de maturidade para avançado | Só após CI verde e estabilidade observada |

## Critério para marcar ready for review

- PR criado em draft.
- Workflows executados.
- Falhas corrigidas por causa raiz.
- Artifacts revisados.
- Documentação viva confirmada.

## Rollback

Remover os workflows novos e o script de guardrails da branch/PR. Não há alteração runtime da aplicação neste incremento.
