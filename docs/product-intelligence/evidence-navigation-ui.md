# Product Intelligence Evidence Navigation UI

## Objetivo

Criar uma camada navegável em modo `review_only` sobre as evidências da frente Product Intelligence, permitindo leitura executiva, navegação por artifact e drill-down técnico sem deploy ou mutação produtiva.

## Capacidades

- HTML autocontido e responsivo.
- Cards por artifact.
- Navegação lateral por âncoras.
- Estado visual por cor:
  - verde: evidência disponível/consolidada;
  - amarelo: requer revisão;
  - vermelho: evidência ausente/bloqueada.
- Saídas JSON, Markdown e HTML.
- Revisão humana obrigatória preservada.

## Saídas runtime

| Arquivo | Finalidade |
|---|---|
| `product-intelligence-evidence-navigation-ui.json` | Payload estruturado para futura UI dinâmica |
| `product-intelligence-evidence-navigation-ui.md` | Sumário operacional |
| `product-intelligence-evidence-navigation-ui.html` | Interface navegável autocontida |

## Guardrails

- Não executa deploy.
- Não altera produção.
- Não chama IA externa.
- Não escreve em sistemas externos.
- Não altera secrets/permissões.

## Próximo incremento recomendado

Evidence Analytics Drill-down Runtime.
