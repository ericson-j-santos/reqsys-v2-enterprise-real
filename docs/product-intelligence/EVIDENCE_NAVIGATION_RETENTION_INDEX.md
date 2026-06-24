# Product Intelligence Evidence Navigation Retention Index

## Objetivo

Criar um índice de retenção para os artifacts review-only da Evidence Navigation UI, garantindo rastreabilidade, política explícita de retenção e bloqueio de uso como evidência produtiva automática.

## Escopo

- Geração de índice JSON de retenção.
- Geração de sumário Markdown.
- Validação de SHA-256 herdado do artifact publisher manifest.
- Upload de artifact de retenção pelo GitHub Actions.
- Retenção padrão: 14 dias.

## Política

| Regra | Valor |
|---|---:|
| Retenção padrão | 14 dias |
| Retenção mínima | 7 dias |
| Retenção máxima review-only | 30 dias |
| Evidência produtiva | Não |
| Revisão humana | Obrigatória |

## Guardrails

- O índice é `review_only`.
- Não publica em produção.
- Não altera secrets.
- Não altera deploy.
- Os artifacts devem ser reproduzíveis por workflow.
- Uso produtivo vinculante exige aprovação humana de governança.
