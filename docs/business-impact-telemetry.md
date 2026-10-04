# Business Impact Telemetry

Objetivo: transformar evidência operacional em métricas de impacto sem inventar ROI.

## Métricas observáveis
- PR → merge: mediana em minutos, somente quando created_at e merged_at existem.
- Falha → recuperação: mediana em minutos, somente quando há timestamps vinculados à mesma recuperação.

## Métricas bloqueadas até fonte objetiva
- taxa de intervenção humana;
- horas poupadas;
- custo por execução;
- ROI percentual.

Essas métricas permanecem `unavailable`; não são inferidas a partir de CI verde, quantidade de commits ou duração de workflow.

## Critério para liberar ROI
Instrumentar eventos explícitos e correlacionados para intervenção humana e automação, custo real do executor/infra e baseline comparável. Só então calcular economia/ROI com amostra e janela documentadas.

A saída canônica é `audit/business-impact/report.json` e deve registrar o SHA da fonte.
