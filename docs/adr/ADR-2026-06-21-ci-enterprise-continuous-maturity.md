# ADR-2026-06-21 — CI Enterprise Continuous Maturity

## Status

Consolidado na arquitetura atual do ReqSys.

## Contexto

O incremento original do PR #70 foi criado para reduzir tempo até feedback, regressões intermitentes e reruns sem causa raiz. A branch histórica acumulou depois alterações de segurança e interface que não pertencem ao escopo principal.

Na reconciliação de 2026-10-04, o objetivo original já está materializado na `main` em versões mais evoluídas. A decisão permanece válida, mas não é seguro restaurar os workflows antigos por cima das superfícies atuais.

## Decisão

Manter uma arquitetura de CI em camadas, com responsabilidades distintas:

| Camada | Superfície canônica atual | Bloqueia PR | Objetivo |
|---|---|---:|---|
| Prontidão antecipada | `Pre-PR Readiness Gate` | Sim | Falhar cedo no HEAD exato antes dos checks caros |
| Fast path | `CI Enterprise Fast` | Sim | Admission controller, guardrails e validações rápidas |
| CI principal | `CI — ReqSys v2 Enterprise` | Sim | Validação aplicável completa por perfil |
| Regressão ampla | `CI Enterprise Regression` | Não por padrão | Regressão nightly/manual e evidências de cobertura/segurança |
| Observabilidade | `CI Observability` | Não substitui gates | Duração e sinais operacionais de CI |
| Merge | `Governed Merge Queue` | Sim | Revalidar SHA, mergeabilidade e workflows obrigatórios |

## Regras canônicas

1. O fast path deve continuar associado ao HEAD atual e não pode reutilizar admissão de SHA anterior.
2. Falha recorrente não é resolvida apenas com rerun: deve gerar causa raiz, teste preventivo ou guardrail quando aplicável.
3. A regressão ampla não deve alongar desnecessariamente o caminho crítico de cada PR.
4. Observabilidade de CI não substitui check obrigatório.
5. Merge deve permanecer protegido por estabilidade do SHA e política de workflows atuais.
6. Dependências e runtimes devem usar versões explícitas compatíveis com os manifests atuais.
7. Guardrails devem reduzir falso positivo sem relaxar segurança em runtime/configuração produtiva.
8. Workflows paralelos com a mesma função não devem ser recriados quando existir superfície canônica equivalente.

## Reconciliação do PR #70

Não são restaurados:

- `.github/workflows/ci-enterprise-observability.yml`, substituído pelo canônico `.github/workflows/ci-observability.yml`;
- mudanças antigas de login Vue/Angular, fora do escopo do CI e em superfícies removidas/evoluídas;
- `security-strong-guardrails.yml` e scanner associado, pois segurança hoje é tratada pelas superfícies canônicas de Security Baseline/Specialized Scanners e governança atual;
- versões históricas de `ci.yml`, `ci-enterprise-fast.yml`, `ci-enterprise-regression.yml` ou `ci_enterprise_guardrails.py`, pois a `main` contém implementações posteriores.

## Consequência

O trabalho legítimo do #70 é preservado como decisão arquitetural e contrato verificável, sem reintroduzir código/workflows antigos que criariam duplicação, conflito ou regressão de governança.
