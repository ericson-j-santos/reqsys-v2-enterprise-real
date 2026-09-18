# Próximo Incremento Recomendado — Estatísticas v2

## Objetivo

Substituir parte dos indicadores locais por dados reais, mantendo o contrato atual e os guard rails.

## Escopo recomendado

1. Criar endpoint backend `GET /api/estatisticas`.
2. Expor indicadores reais de:
   - requisitos;
   - GitHub Actions;
   - PRs;
   - runtime de conectores;
   - segurança/guard rails.
3. Criar registry de fontes externas autorizadas.
4. Adicionar TTL e validação de expiração de fonte externa.
5. Criar E2E responsivo da rota `/estatisticas`.
6. Criar gate para impedir deploy quando mock externo estiver marcado como real.

## Decisão recomendada

Priorizar primeiro dados reais internos, depois fontes externas. Isso reduz risco de confiabilidade e evita decisões operacionais baseadas em fonte externa ainda não auditada.
