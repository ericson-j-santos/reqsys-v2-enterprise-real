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
- `RequisitosView.vue` passou a consumir query string e aplicar filtros analíticos por status, urgência, área e busca textual.
- Tela de requisitos agora exibe total filtrado, estado de filtro ativo, alerta de resultado vazio e botão para limpar filtros.
- Responsividade ajustada na área de filtros e tabela para telas menores.

## Critérios atendidos

- [x] Card do dashboard abre analítico filtrado por status.
- [x] Query string é preservada na URL.
- [x] Tela de requisitos lê filtros vindos da URL.
- [x] Usuário consegue limpar filtros.
- [x] Estado visual de filtro ativo foi adicionado.
- [x] Lógica de filtro foi isolada em helper testável.
- [x] Teste unitário do helper foi adicionado.

## Validação pendente

- Executar `npm run test:unit` em ambiente local ou CI.
- Executar `npm run build` no frontend.
- Validar visualmente desktop, tablet e mobile.

## Próximo incremento recomendado

Aplicar o mesmo padrão de analítico clicável no Painel de Integração, com filtros por origem, status, erro, data e correlation_id.
