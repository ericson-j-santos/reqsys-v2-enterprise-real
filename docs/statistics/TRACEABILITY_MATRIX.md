# Matriz de Rastreabilidade — Aba Estatísticas

| Requisito | Implementação | Teste | Documentação |
|---|---|---|---|
| Criar aba de estatísticas | `frontend/src/views/EstatisticasView.vue` | `frontend/src/services/__tests__/estatisticas.test.js` | `IMPLEMENTATION_NOTES.md` |
| Registrar navegação | `frontend/src/router/index.js`, `frontend/src/layouts/AppLayout.vue` | build/smoke pendente CI | `VALIDATION_REPORT.md` |
| Separar dados internos e externos | `frontend/src/services/estatisticas.js` | contrato dos indicadores | `OPERATING_MODEL.md` |
| Exigir fonte e fórmula | `validarIndicador` | bloqueio sem fonte/fórmula | `INTEGRATION_CHECKLIST.md` |
| Evitar promoção indevida de maturidade | `validarIndicador` | estado avançado exige evidência | `STATUS.md` |
| Preparar próximo incremento | `NEXT_INCREMENT.md` | pendente | `RELEASE_NOTE.md` |
