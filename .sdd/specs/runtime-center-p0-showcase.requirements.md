# Runtime Operational Center P0 — showcase estático

## Objetivo

Preservar o material visual do PR #76 sem promovê-lo a fonte de verdade operacional.

## Requisitos

1. O conteúdo deve ser explicitamente marcado como demonstração estática.
2. Estados e métricas fixos não podem ser apresentados como evidência atual.
3. O contrato deve declarar `mode=illustrative` e `operational_evidence=false`.
4. Health, timeline, indicadores, arquitetura e incidentes do conceito P0 devem permanecer visíveis.
5. O material deve apontar para APIs canônicas quando o usuário precisar de evidência real.
6. Nenhum deploy, promoção de ambiente ou mutação de runtime faz parte deste incremento.
7. O teste preventivo deve impedir que o showcase volte a parecer evidência operacional real.

## Critérios de aceite

- teste contratual verde;
- SDD e governança verdes;
- `behind_by=0`;
- PR sem conflitos;
- nenhum dado estático usado para decisão operacional.
