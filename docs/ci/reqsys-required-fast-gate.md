# ReqSys Required Fast Gate

## Objetivo

Reduzir o tempo de espera operacional em PRs pequenos criando um gate canônico, rápido e determinístico para o caminho crítico de merge.

Este gate não remove workflows existentes. Ele cria um check candidato para branch protection, permitindo que validações report-only, dashboards, evidências históricas e smokes pesados continuem existindo sem bloquear todo PR por padrão.

## Escopo do gate

O workflow `.github/workflows/reqsys-required-fast-gate.yml` executa somente validações essenciais:

- identifica arquivos alterados;
- compila arquivos Python alterados em `backend/`, `scripts/` e `tests/`;
- valida o contrato mínimo do próprio workflow;
- compila o validador de segurança baseline quando disponível;
- cancela execuções obsoletas no mesmo ref.

## Política Pareto

| Tipo de validação | Caminho crítico de PR | Recomendação |
|---|---:|---|
| Gate rápido obrigatório | Sim | `ReqSys Required Fast Gate` |
| CI completo | Condicional | Manter em PRs relevantes e `main` |
| Segurança baseline | Sim, mínimo | Manter smoke rápido no gate e scanner completo separado |
| Dashboards e evidências históricas | Não | Rodar em `main`, `schedule` ou `workflow_dispatch` |
| Smokes públicos/deploy | Não em PR comum | Rodar pós-merge ou sob aprovação |

## Próxima ação operacional

Após o workflow estabilizar verde por alguns PRs, avaliar branch protection para exigir somente o check canônico rápido no caminho crítico e manter os demais checks como informativos ou condicionais por path.

## Rollback

Remover:

- `.github/workflows/reqsys-required-fast-gate.yml`
- `docs/ci/reqsys-required-fast-gate.md`
