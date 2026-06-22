# Governança de Dados — Aba Estatísticas v1

## Dados internos

Dados internos são métricas derivadas da própria solução, como requisitos, CI/CD, PRs, runtime, logs e auditoria. Na v1, há fonte local inicial para preservar contrato e layout.

## Dados externos

Dados externos só podem ser usados quando houver:

- fonte identificada;
- data de coleta;
- TTL;
- confiabilidade;
- versão do conector;
- separação visual na UI;
- trilha de auditoria.

## Classificação de confiabilidade

| Nível | Uso permitido |
|---|---|
| alta | Pode apoiar decisão operacional |
| media | Pode apoiar análise com revisão |
| baixa | Apenas referência exploratória |

## Política atual

Fontes externas permanecem como `nao_medido` até a implementação de registry/conector real.
