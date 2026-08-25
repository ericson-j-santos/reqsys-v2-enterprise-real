# Racionalização de ferramentas e superfícies do ReqSys

Data de referência: 2026-08-25

## Objetivo

Reduzir duplicação tecnológica e custo operacional sem remover componentes ainda usados por CI, E2E, documentação ou operação.

A fonte estruturada desta decisão é `governance/tooling/rationalization-inventory.json`.

## Estado evidenciado

| Superfície | Decisão | Estado | Destino |
|---|---|---|---|
| `frontend` | MANTER | Canônico de produto e deploy | `frontend` |
| `frontend-vuetify` | CONSOLIDAR | Legado ainda usado por E2E | `frontend` |
| `frontend-angular` | CONSOLIDAR | Legado ainda usado por E2E | `frontend` |
| `docs-site` | MANTER | Fonte canônica do MkDocs | `docs-site` |
| `docs/ops-dashboard` | MANTER | Dashboard operacional canônico | `docs/ops-dashboard` |
| `ops-dashboard` | CONSOLIDAR | HTMLs estáticos históricos | `docs/ops-dashboard` |

## Decisão arquitetural

### 1. Frontend canônico

`frontend/` passa a ser tratado explicitamente como a única superfície de produto em evolução.

Critérios usados:

- possui configuração de deploy Fly.io para os ambientes do produto;
- concentra as evoluções recentes do ReqSys;
- utiliza Vue/Vite/Vuetify e já absorveu capacidades que existiam no frontend Vuetify paralelo;
- contém a rota pública `/showcase` introduzida no ReqSys Showcase v1.

A partir deste inventário, `frontend-angular/` e `frontend-vuetify/` não devem receber novas funcionalidades de negócio. Mudanças nesses diretórios devem ser restritas a migração, compatibilidade necessária ou retirada governada.

### 2. Frontends paralelos

A remoção imediata é bloqueada porque o `playwright.config.ts` raiz ainda inicia:

- `frontend-vuetify` em `localhost:5174`, com projeto E2E `vuetify`;
- `frontend-angular` em `localhost:4200`, com projeto E2E `angular`.

Portanto, ambos estão em estado **CONSOLIDAR**, não **REMOVER**.

Ordem recomendada:

1. inventariar os cenários `e2e/*vuetify.spec.ts` e `e2e/*angular.spec.ts`;
2. classificar cada caso como requisito vigente, duplicado ou obsoleto;
3. portar somente a cobertura vigente para `frontend/`;
4. retirar os webServers/projetos legados do Playwright raiz;
5. retirar referências em scripts e workflows;
6. executar CI completo;
7. somente então excluir os diretórios em PR separada.

## 3. Documentação

`docs-site/` deve permanecer porque `mkdocs.yml` define explicitamente `docs_dir: docs-site` e o site do ReqSys é construído a partir dessa árvore.

A pasta `docs/` não deve ser removida por este inventário: ela contém runbooks, evidências e dashboards operacionais que não são equivalentes ao conteúdo editorial do MkDocs. A racionalização entre `docs/` e `docs-site/` deve ocorrer por conteúdo, não por exclusão de diretório.

## 4. Dashboard operacional

`docs/ops-dashboard/` é registrado explicitamente como a superfície canônica de dashboard operacional, conforme o runbook `docs/runbooks/ops-dashboard.md` e o workflow `Ops Dashboard`.

O diretório raiz `ops-dashboard/` contém duas superfícies HTML históricas:

- `ops-dashboard/movimento-email/index.html`;
- `ops-dashboard/teams-notification/index.html`.

Esses arquivos devem ser consolidados no dashboard canônico ou substituídos por módulos do frontend principal. A remoção fica bloqueada até que referências e consumidores ativos sejam zerados.

## Guardrails

- Cada categoria declarada em `canonical_targets` deve possuir exatamente um item canônico.
- Todo item canônico deve permanecer em decisão `MANTER`.
- Nenhuma superfície marcada `CONSOLIDAR` pode ser removida enquanto `blocking_dependencies` não estiver vazio.
- Nenhuma nova feature deve ser criada em `frontend-angular/` ou `frontend-vuetify/`.
- `frontend/` é o único destino de novas capacidades de UI de produto.
- `docs-site/` é a fonte do MkDocs.
- `docs/ops-dashboard/` é o destino canônico de dashboards operacionais estáticos.
- Toda retirada deve ocorrer em PR separada, com CI verde e evidência de zero referências ativas.

## Próximo incremento

Executar **Fase 1 — consolidação E2E**:

1. listar todos os testes `*angular.spec.ts` e `*vuetify.spec.ts`;
2. comparar cenários equivalentes contra a aplicação `frontend/`;
3. criar uma matriz `MIGRAR / DESCARTAR / JÁ COBERTO`;
4. portar o primeiro lote Pareto de cenários vigentes para o frontend canônico;
5. manter os diretórios legados até que a matriz atinja zero dependências obrigatórias.
