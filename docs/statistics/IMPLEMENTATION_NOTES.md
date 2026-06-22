# Implementação — Aba Estatísticas v1

Data: 2026-06-21
Branch: `feature/estatisticas-tab-v1`

## Entregas funcionais

- Rota `/estatisticas` registrada no Vue Router.
- Item `Estatísticas` adicionado ao menu principal.
- Tela `EstatisticasView.vue` com:
  - cards executivos;
  - filtros por categoria, tipo de fonte e estado atual;
  - cards analíticos por indicador;
  - tabela consolidada;
  - exibição de fonte, fórmula, coleta, confiabilidade, evidências e pendências.
- Serviço `estatisticas.js` com:
  - indicadores internos iniciais;
  - indicador externo inicial como não medido;
  - validação de guard rails;
  - cálculo de resumo consolidado.
- Teste unitário `estatisticas.test.js` para:
  - validar contrato dos indicadores iniciais;
  - bloquear indicador sem fonte/fórmula;
  - impedir promoção indevida de estado avançado sem evidência.

## Decisão aplicada

A implementação é internal-first. Informações externas entram inicialmente como registry pendente e estado `nao_medido`, para evitar falsa maturidade ou uso de dado externo sem fonte auditável.

## Pendências planejadas

- Conectar indicadores reais de requisitos, CI/CD, PRs e runtime.
- Criar backend/endpoint para fontes externas autorizadas.
- Adicionar E2E responsivo específico da rota `/estatisticas`.
- Adicionar quality gate para bloquear mocks em produção.
