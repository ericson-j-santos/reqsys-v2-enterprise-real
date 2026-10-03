# Executive Promotion Advisor — homologação pós-artifact

## Objetivo

Validar o artifact canônico `ops-dashboard-static` após a execução do workflow `Ops Dashboard`, confirmando simultaneamente:

- presença única do card visual;
- contrato `cards.executive_promotion_advisor`;
- guardrails report-only;
- evidência da URL pública, quando configurada;
- histórico acumulado de estabilidade.

## Decisões

- `HOMOLOGATED`: artifact e URL pública validados.
- `ARTIFACT_HOMOLOGATED_PUBLIC_PENDING`: artifact válido, URL pública não configurada ou ainda não observada.
- `REVIEW`: artifact válido, porém a superfície pública falhou.
- `BLOCKED`: artifact ou contrato inválido.

Todas as decisões permanecem com `production_blocker=false` e exigem aprovação humana.

## Histórico

O artifact `executive-promotion-advisor-homologation-history` mantém até 50 amostras e calcula:

- taxa de sucesso do artifact;
- taxa de sucesso da URL pública;
- taxa de homologação completa;
- sequência estável;
- elegibilidade para futura revisão do gate.

A elegibilidade exige pelo menos 30 amostras, 98% de homologação completa e sequência estável mínima de 20 execuções. Ela não promove o gate automaticamente.

## Configuração pública

A URL pode ser informada manualmente no `workflow_dispatch` ou pela variável de repositório `EXECUTIVE_PROMOTION_ADVISOR_PUBLIC_URL`.
