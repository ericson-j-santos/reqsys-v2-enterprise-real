# Visual Regression Governance

## Objetivo

Criar a fundação para detectar regressões visuais silenciosas no frontend enterprise do ReqSys.

## Estratégia recomendada

- Playwright screenshot snapshots.
- Baseline versionada.
- Comparação percentual.
- Aprovação humana para mudança visual intencional.
- Artifact visual no CI.

## Escopo futuro sugerido

- Login.
- Dashboard executivo.
- Runtime dashboard.
- Navegação lateral.
- Tabelas críticas.
- Responsividade mobile.

## Critério de maturidade

Este incremento cria apenas a estrutura documental e o local canônico para evolução dos testes visuais. O gate bloqueante de regressão visual deve ser implementado em incremento separado para evitar risco operacional no CI atual.
