# ReqSys — Varredura Técnica Padrão Ouro — 2026-06-20

> Repositório: `ericson-j-santos/reqsys-v2-enterprise-real`  
> Branch avaliada: `main`  
> Ambiente observado: GitHub / código-fonte  
> Ambiente de aplicação deste incremento: documentação e frontend em branch de trabalho  
> Produção: sem alteração direta

## 1. Escopo da varredura inicial

Foram avaliados sinais estruturais do frontend, rotas, dashboard, requisitos, documentação e scripts de testes disponíveis.

Arquivos observados neste primeiro ciclo:

- `frontend/package.json`
- `frontend/src/router/index.js`
- `frontend/src/views/DashboardView.vue`
- `frontend/src/views/RequisitosView.vue`
- `frontend/src/views/ArquiteturaView.vue`
- `docs/REQSYS_PADRAO_OURO_TRANSVERSAL.md`

## 2. Achados objetivos

### 2.1 Frontend e abas

O router contém as principais abas operacionais do ReqSys:

- Login
- Dashboard
- Requisitos
- Rastreabilidade
- Auditoria
- Pipeline
- Relatórios
- Segredos
- Qualidade IA
- Recomendações IA
- Task Console
- Specs
- Hub Low-Code
- Painel de Integração
- Arquitetura
- GovBI IA

### 2.2 Dashboard

O dashboard já possui:

- Cards de métricas.
- Chip de ambiente.
- Rotas de detalhe por card.
- Tooltips.
- Pipeline operacional.
- Endpoints críticos.

Lacuna identificada:

- Cards direcionam para módulos, mas nem todos preservam filtro analítico via URL.
- O clique do card ainda não garante analítico filtrado em todas as telas de destino.

### 2.3 Requisitos

A tela de requisitos possui:

- Listagem tabular.
- Cadastro guiado.
- Assistente IA.
- Cards de resumo.
- Responsividade básica por Vuetify grid.

Lacunas identificadas:

- Falta barra de filtros analíticos por status, urgência, área e busca textual.
- Falta leitura de query string para abrir a tela já filtrada a partir do dashboard.
- Falta estado explícito de filtro ativo.
- Falta botão de limpar filtros.
- Falta visualização alternativa para lista em telas menores.

### 2.4 Testes

O `package.json` possui scripts de build e Playwright, mas ainda não expõe script explícito de teste unitário Vitest.

Lacuna:

- Criar `test:unit` e teste mínimo para a lógica de filtro analítico.

## 3. Incremento recomendado neste ciclo

Aplicar primeiro incremento seguro e de baixo risco:

1. Introduzir helper puro de filtros analíticos de requisitos.
2. Atualizar `RequisitosView.vue` para aceitar query string e filtrar lista.
3. Atualizar `DashboardView.vue` para enviar filtros via URL nos cards aplicáveis.
4. Adicionar teste unitário da lógica de filtros.
5. Expor script `test:unit`.
6. Registrar PR com ambiente, escopo, riscos e evidências.

## 4. Critérios de aceite do incremento

- [ ] Dashboard envia filtros por query string para o módulo de requisitos.
- [ ] Tela de requisitos lê query string e aplica filtro inicial.
- [ ] Usuário consegue limpar filtros.
- [ ] Filtro funciona por status, urgência, área e busca textual.
- [ ] Lógica testada por Vitest.
- [ ] Build não deve ser impactado.
- [ ] Produção não deve receber alteração direta.

## 5. Próximos incrementos após este ciclo

1. Painel de Integração: drill-down por erro, origem, status, correlation_id e data.
2. GovBI IA: analítico de pesquisas com erro, fonte, latência, fallback e evidência.
3. Pipeline: analítico por etapa, duração, falha, reprocessamento e responsável.
4. Task Console/Planner: histórico de envio, retorno, falha e reprocessamento.
5. Responsividade global: revisão visual das 16 rotas do router.
6. CI/CD: gates de produção com testes unitários, e2e, lint/build e documentação.
