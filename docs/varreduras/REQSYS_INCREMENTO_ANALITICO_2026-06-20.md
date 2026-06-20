# ReqSys — Incremento Analítico Inicial — 2026-06-20

## Ambiente

- Observado: GitHub / branch `main`.
- Aplicação: branch `docs/padrao-ouro-transversal-reqsys`.
- Produção: sem alteração direta.

## Aplicado

- Dashboard passou a direcionar cards para rotas analíticas com query string.
- Criado helper puro de filtros de requisitos.
- Criado teste unitário do helper.
- Adicionado script `npm run test:unit`.
- Changelog atualizado.

## Pendência técnica

A aplicação dos filtros diretamente em `RequisitosView.vue` deve seguir em incremento próprio, pois a escrita completa do arquivo foi bloqueada pelo conector neste ciclo.

## Próximo incremento recomendado

Implementar consumo de query string em `RequisitosView.vue`, exibindo filtros por status, urgência, área e busca textual, com botão para limpar filtros e estado visual de filtro ativo.
