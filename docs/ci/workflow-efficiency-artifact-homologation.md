# Homologação do artifact Workflow Efficiency

## Objetivo

Validar o card `Workflow Efficiency` no artifact real `ops-dashboard-static`, após a conclusão bem-sucedida do workflow `Ops Dashboard`.

## Fluxo

1. O workflow `Ops Dashboard` gera e publica `ops-dashboard-static`.
2. `Workflow Efficiency Artifact Homologation` é acionado por `workflow_run`.
3. O artifact da execução fonte é baixado.
4. O homologador valida:
   - presença de `index.html`;
   - presença de `data/runtime-executive-index.json`;
   - existência única do card visual;
   - hook de renderização;
   - consumo de `cards.workflow_efficiency`;
   - link canônico `links.workflow_efficiency`;
   - ausência de chamadas `fetch` externas introduzidas pelo card.
5. A evidência JSON é publicada por 30 dias.

## Decisões

- `HOMOLOGATED`: artifact completo e contrato presente.
- `BLOCKED`: arquivo, token visual, card ou link canônico ausente.

## Evidência

Artifact: `workflow-efficiency-artifact-homologation`

Arquivo: `evidence.json`

A evidência inclui `correlation_id`, checks executados, hashes SHA-256, resumo do card e erros encontrados.

## Guardrails

- Somente leitura do artifact fonte.
- Nenhuma alteração de deploy, merge queue, auto-merge ou branch protection.
- Nenhuma chamada externa no runtime público.
- Fonte única preservada: `runtime-executive-index.json`.
- Execução manual disponível mediante `run_id` para revalidação auditável.
