# ReqSys - projecao estatistica de conclusao

Este documento registra como a projecao executiva de conclusao passa a ser publicada pelo produto.

## Fonte canonica

- Dados versionados: `docs/analytics/reqsys_projecao_estatistica_conclusao.json`
- API consumidora: `GET /v1/estatisticas`
- Bloco publicado no snapshot: `projecaoConclusao`
- Tela consumidora: `frontend/src/views/EstatisticasView.vue`

## O que o bloco entrega

- referencia temporal da leitura executiva;
- maturidade media consolidada por dimensao;
- percentuais reais de conclusao;
- cenarios conservador e acelerado com janela em dias;
- gargalos, riscos, tendencias e aceleradores;
- leitura executiva com forcas atuais e faltantes.

## Como atualizar

1. Ajuste o JSON versionado com a nova referencia temporal.
2. Revise percentuais reais, gaps, probabilidades e cenarios.
3. Execute testes focados de backend e frontend para validar o contrato.
4. Valide a tela `/estatisticas` para confirmar a leitura executiva e o drill-down.

## Guard rails

- Manter formula, fonte e confiabilidade explicitas nos indicadores derivados.
- Nao usar a projecao como substituto de evidencias reais de CI ou producao.
- Atualizar a referencia temporal sempre que a leitura executiva mudar de base.
