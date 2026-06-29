# Parallel PR Queue

## Objetivo

Aumentar a vazão de PRs sem criar conflito estrutural ou PR impossível de mergear.

## Regra operacional

Abrir PRs paralelos apenas quando cada PR alterar caminho exclusivo e domínio desacoplado.

## Lanes seguras (estratégia ativa)

| Lane | Domínio | Risco |
| --- | --- | --- |
| A — OpenAPI Evolution | Spectral, Postman, Newman, workflows `openapi-*` | Baixo |
| B — Docs Runtime Governance | `docs/audit/`, evidence hub, cards executivos | Muito baixo |
| C — Contract Sync | drift routes ↔ OpenAPI (report-only) | Médio/baixo |
| D — Observabilidade | `merge-lane-priority`, índices ops-dashboard | Baixo |

Índice machine-readable: `artifacts/parallel-pr-governance/safe-lanes.json`.  
Runbook completo: `docs/runbooks/parallel-lanes-strategy.md`.

Lanes genéricas ainda válidas:

- Documentação.
- Evidências versionadas.
- Runbooks.
- Contratos de dashboard.
- Dados operacionais estáticos.

## Lanes bloqueadas enquanto houver PRs abertos concorrentes

- Runtime backend.
- Dashboard frontend.
- Workflows principais.
- Contratos compartilhados.
- Dependências globais.

## Critério de abertura de novo PR

1. `main` atualizada como base.
2. Caminho exclusivo.
3. Sem edição em arquivos já tocados por PR aberto.
4. Escopo com no máximo 1 responsabilidade.
5. CI verde antes de recomendar merge.

## Critério de pausa

Pausar abertura de PRs quando:

- PR ficar atrás da `main` e tocar arquivo concorrente;
- checks obrigatórios ficarem instáveis;
- o mesmo domínio já tiver PR aberto;
- houver risco de conflito em runtime, frontend, workflows ou contratos globais.
