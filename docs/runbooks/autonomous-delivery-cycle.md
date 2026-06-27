# Autonomous Delivery Cycle — ciclo governado de entrega contínua

## Objetivo

Automatizar, com guardrails, o ciclo:

1. localizar PRs candidatos;
2. validar se tudo está verde;
3. executar merge somente quando explicitamente autorizado;
4. observar CI pós-merge em `main`;
5. capturar próximos incrementos naturais para continuidade no chat/agente.

## Arquivo principal

- `.github/workflows/autonomous-delivery-cycle.yml`

## Modelo operacional

O ciclo é conservador por padrão.

Para um PR ser processado, precisa atender a todos os critérios:

| Critério | Regra |
|---|---|
| Base | `main` |
| Estado | PR aberto e não draft |
| Mergeability | `mergeable != false` |
| Autorização explícita | label `cycle:auto-merge-approved` |
| Fila governada | label `merge-queue:eligible` |
| CI obrigatório | todos os workflows obrigatórios concluídos com `success` |
| Estratégia de merge | squash merge com SHA esperado |
| Pós-merge | observação de runs `push` no commit mergeado |

## Workflows obrigatórios

- `CI Enterprise Fast`
- `CI — ReqSys v2 Enterprise`
- `Governance Quality Gates`
- `Governança Padrão Ouro`
- `Branch Protection Audit`
- `PR Conflict Guard`
- `Governed Merge Queue`

## Modos

### Dry-run

Execução manual sem merge:

```text
Actions → Autonomous Delivery Cycle → Run workflow → dry_run=true
```

Uso recomendado para validar elegibilidade antes de ativar o ciclo real.

### Merge enabled

Execução manual com merge:

```text
Actions → Autonomous Delivery Cycle → Run workflow → dry_run=false
```

Também existe execução agendada a cada 30 minutos. Mesmo no agendamento, o merge continua condicionado às labels e aos workflows verdes.

## Evidências publicadas

O workflow publica o artifact:

- `autonomous-delivery-cycle-report`

Com os arquivos:

- `artifacts/autonomous-delivery-cycle/delivery-cycle-report.json`
- `docs/ops-dashboard/data/autonomous-delivery-cycle-latest.json`

## Próximos incrementos

O ciclo tenta extrair próximos incrementos a partir do corpo do PR, procurando seções como:

- `Próximo incremento natural`
- `Próximas ações`
- `Next increment`

Os itens capturados são gravados em `next_increments` com status `queued_for_chat_execution`.

## O que não faz

- Não mergeia PR sem label explícita.
- Não ignora CI vermelho.
- Não faz force merge.
- Não corrige falhas automaticamente.
- Não executa próximo incremento sozinho.
- Não substitui revisão humana em PRs de risco alto.

## Decisão recomendada

Usar o ciclo em três níveis:

1. **Agora:** dry-run para validar elegibilidade.
2. **Após estabilidade:** aplicar `cycle:auto-merge-approved` apenas em PRs pequenos, report-only e mergeáveis.
3. **Padrão ouro:** consumir `autonomous-delivery-cycle-latest.json` no dashboard operacional e no coordenador de próximos incrementos.
