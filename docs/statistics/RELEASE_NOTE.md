# Release Note — Aba Estatísticas v1

## Tipo

Feature / Analytics / Governança

## Resumo

Adiciona uma aba operacional `/estatisticas` ao ReqSys para consolidar indicadores internos evidenciados e preparar o uso governado de informações externas auditáveis.

## Impacto funcional

- Usuário passa a ter uma tela própria para acompanhar estatísticas da solução.
- Indicadores exibem estado atual, estado alvo, tendência, fonte, fórmula, confiabilidade, evidências e pendências.
- Dados externos começam como `nao_medido`, evitando falsa promoção de maturidade.

## Impacto técnico

- Novo serviço frontend `frontend/src/services/estatisticas.js`.
- Nova view `frontend/src/views/EstatisticasView.vue`.
- Nova rota `/estatisticas`.
- Novo item no menu lateral.
- Novo teste unitário de guard rails.

## Riscos conhecidos

- Indicadores ainda usam fonte local inicial para dados internos.
- Fontes externas reais ainda dependem de conector/registry backend.
- E2E responsivo ainda precisa ser executado no CI.

## Próximo incremento recomendado

Conectar os indicadores reais de requisitos, GitHub Actions, PRs e runtime, mantendo o mesmo contrato e adicionando quality gate para bloquear mock em produção.
