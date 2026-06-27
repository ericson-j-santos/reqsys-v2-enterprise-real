# Runtime Operational Evidence UI

## Objetivo

Criar uma interface navegável em modo `review_only` sobre o grafo JSON de evidências operacionais, permitindo leitura executiva, navegação por nó e drill-down de correlações temporais sem deploy ou mutação produtiva.

## Pré-requisito

- `runtime-operational-evidence-graph.json` gerado por `generate_runtime_operational_evidence_graph.py`.

## Capacidades

- HTML autocontido e responsivo.
- Cards por nó do grafo.
- Navegação lateral por âncoras.
- Tabela de arestas com correlações temporais.
- Estado visual por cor:
  - verde: nó consolidado com correlação operacional/CI/governança;
  - amarelo: requer revisão;
  - vermelho: bloqueado ou ausente.
- Saídas JSON, Markdown e HTML.
- Revisão humana obrigatória preservada.

## Saídas runtime

| Arquivo | Finalidade |
|---|---|
| `runtime-operational-evidence-ui.json` | Payload estruturado para consumo dinâmico |
| `runtime-operational-evidence-ui.md` | Sumário operacional |
| `runtime-operational-evidence-ui.html` | Interface navegável autocontida |

## Guardrails

- Não executa deploy.
- Não altera produção.
- Não chama IA externa.
- Não escreve em sistemas externos.
- Não altera secrets/permissões.

## Workflow

- **Arquivo:** `.github/workflows/runtime-operational-evidence-ui.yml`
- **Trigger:** PR em `tools/product_intelligence/**`, `docs/operations/**`
- **Modo:** report-only

## Próximo incremento recomendado

Runtime Evidence Graph Dashboard Integration — integrar o grafo e a UI ao Ops Dashboard e ao Operational Evidence Hub com drill-down unificado.
