# Autonomous Delivery Cycle

## Objetivo

Automatizar, com guardrails, o ciclo:

1. localizar PRs candidatos;
2. validar se tudo está verde;
3. executar merge somente quando explicitamente autorizado;
4. observar CI pós-merge em `main`;
5. capturar próximos incrementos naturais para continuidade no chat/agente.

## Workflow

- `.github/workflows/autonomous-delivery-cycle.yml`

## Critérios obrigatórios

| Critério | Regra |
|---|---|
| Base | `main` |
| Estado | PR aberto e não draft |
| Autorização explícita | label `cycle:auto-merge-approved` |
| Fila governada | label `merge-queue:eligible` |
| CI obrigatório | workflows obrigatórios concluídos com `success` |
| Estratégia de merge | squash merge com SHA esperado |
| Pós-merge | observação dos runs `push` |

## Não faz

- Não mergeia PR sem label explícita.
- Não ignora CI vermelho.
- Não faz force merge.
- Não corrige falhas automaticamente.
- Não executa próximo incremento sozinho.

## Primeiro uso

Após merge deste incremento, executar manualmente com:

```text
dry_run=true
required_label=cycle:auto-merge-approved
max_prs=1
```
