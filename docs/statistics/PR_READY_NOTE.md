# Nota para PR Draft — Aba Estatísticas v1

## Situação

Branch implementada e comparada contra `main` sem atraso no momento da validação.

## Razão para draft

- CI ainda precisa executar.
- Build/testes ainda precisam confirmar compatibilidade.
- Há PRs paralelos que também podem alterar frontend/router/layout.

## Solicitação ao CI/revisão

Validar especialmente:

- compilação da nova rota;
- compatibilidade dos componentes Vuetify usados;
- descoberta do teste `estatisticas.test.js`;
- ausência de regressão no menu lateral;
- ausência de promoção indevida de maturidade.
