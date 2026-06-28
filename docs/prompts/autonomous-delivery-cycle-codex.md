# Prompt Codex — Continuidade após Autonomous Delivery Cycle

```text
Contexto:
O repositório possui o workflow Autonomous Delivery Cycle, que valida PRs verdes, exige labels explícitas, executa squash merge governado e publica fila report-only de próximos incrementos.

Arquivos de referência:
- .github/workflows/autonomous-delivery-cycle.yml
- docs/ops-dashboard/data/autonomous-delivery-cycle-latest.json
- docs/ops-dashboard/data/autonomous-delivery-cycle-next-increments.json
- docs/runbooks/autonomous-delivery-cycle.md
- docs/architecture/autonomous-delivery-cycle.md

Tarefa:
Implemente o próximo incremento seguro:
- consumir os contratos do Autonomous Delivery Cycle no dashboard operacional;
- exibir cards de estado do ciclo, PR candidato, bloqueios, CI pós-merge e fila de próximos incrementos;
- manter fallback seguro se os JSONs não existirem;
- não alterar lógica de merge;
- não automatizar execução de novos incrementos;
- adicionar testes/validações de contrato quando aplicável.

Critérios:
- mudança pequena;
- sem conflito com workflows existentes;
- CI verde;
- evidência navegável;
- changelog atualizado;
- próximo incremento natural registrado.
```
