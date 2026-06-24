# Product Intelligence Backlog Publisher Governado

## Objetivo

Gerar pacote de publicação governada para backlog funcional do ReqSys sem escrita automática em sistemas externos.

## Capacidades implementadas

- Publisher governado em modo review package only.
- Manifest JSON de publicação.
- Markdown pronto para GitHub Issues.
- Markdown pronto para Redmine.
- Resumo executivo do pacote.
- HTML de revisão.
- Workflow CI dedicado.
- Artifact de publicação governada.

## Saídas

| Artifact | Uso |
|---|---|
| `product-intelligence-backlog-publisher-manifest.json` | Manifest governado |
| `product-intelligence-backlog-publisher-github-ready.md` | Conteúdo pronto para revisão em GitHub Issues |
| `product-intelligence-backlog-publisher-redmine-ready.md` | Conteúdo pronto para revisão em Redmine |
| `product-intelligence-backlog-publisher-summary.md` | Resumo executivo |
| `product-intelligence-backlog-publisher.html` | Visual HTML |

## Governança

- Escrita externa desabilitada.
- Execução de agente desabilitada.
- Revisão humana obrigatória.
- Pacote apenas para publicação manual.
- Rastreabilidade por correlation_id.

## Limites

- Não cria GitHub Issues automaticamente.
- Não cria Redmine automaticamente.
- Não executa agentes automaticamente.
- Não altera runtime produtivo.
- Não substitui aprovação humana.

## Próximo incremento recomendado

Product Intelligence Backlog Governance Gate.
