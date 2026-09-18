# ADR-0024 — Substituir CodeRabbit por PR Quality Review proprio

## Status

Aprovado para implementacao incremental.

## Contexto

O repositório vinha usando CodeRabbit como apoio de revisão automatizada de PRs. Foram observados alertas operacionais como `Review limit reached`, revisões ignoradas por PR em draft e aumento de ruído em notificações.

O objetivo é manter o passo de revisão automatizada, mas sem dependência externa, sem limite de quota e com maior previsibilidade operacional.

## Decisão

Substituir o CodeRabbit por um workflow próprio:

- `.github/workflows/pr-quality-review.yml`
- `scripts/pr_quality_review.py`

A configuração `.coderabbit.yaml` deixa de ser fonte ativa de governança e passa a documentar a desativação operacional.

## O que o novo workflow cobre

| Dimensão | Cobertura |
|---|---|
| Tamanho do PR | linhas alteradas e quantidade de arquivos |
| Escopo | arquivos alterados e flags por tipo |
| Caminhos críticos | workflows, infra, segurança e auth |
| Segurança | nomes de arquivos potencialmente sensíveis |
| Testes | presença de arquivos de teste quando há código |
| Documentação | identificação de docs alteradas |
| Evidência | relatório JSON e Markdown como artifact |
| Comentário no PR | disponível via `workflow_dispatch` |

## Política de bloqueio

- `critical`: falha o workflow e bloqueia merge.
- `warning`: mantém visível para decisão humana, sem bloquear por padrão.
- `ok`: sem bloqueio objetivo pelo PR Quality Review.

## Benefícios esperados

- Elimina limite externo de review.
- Reduz ruído de bot em PRs draft.
- Mantém revisão objetiva e rastreável.
- Integra com GitHub Actions e artifacts.
- Evita dependência de IA externa para gates operacionais.

## Consequências

Perde-se revisão textual linha a linha gerada por IA externa. Em troca, ganha-se controle, determinismo e previsibilidade. Revisões humanas continuam necessárias para arquitetura, segurança, produção, dados sensíveis e mudanças estruturais.

## Próximos incrementos

- Evoluir o PR Quality Review para consultar status dos checks obrigatórios.
- Incluir checklist por tipo de mudança.
- Publicar sumário executivo em comentário somente quando o PR estiver pronto para revisão.
- Integrar com dashboards operacionais do ReqSys.
