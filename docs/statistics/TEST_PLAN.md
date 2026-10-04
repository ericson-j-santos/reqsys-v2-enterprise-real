# Plano de Testes — Aba Estatísticas

## Unitários

Comando sugerido no frontend:

```bash
npm test -- estatisticas
```

Validações esperadas:

- contrato dos indicadores iniciais válido;
- bloqueio de indicador sem fonte;
- bloqueio de indicador sem fórmula;
- bloqueio de estado avançado sem evidências suficientes;
- cálculo de resumo consolidado preservando estado atual evidenciado.

## Build

```bash
npm run build
```

Validações esperadas:

- import da nova view resolvido;
- rota `/estatisticas` compilada;
- componentes Vuetify utilizados sem erro de template;
- serviço `estatisticas.js` incluído no bundle.

## E2E mínimo recomendado

```bash
npx playwright test frontend/tests/e2e/responsividade.spec.js
```

Incremento futuro recomendado: criar `frontend/tests/e2e/estatisticas.spec.js` para validar navegação, cards, filtros e tabela analítica em desktop/mobile.
