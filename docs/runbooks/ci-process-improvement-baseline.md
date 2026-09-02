# Baseline de melhoria de processo do CI

## Estado

Baseline congelado a partir da primeira execução real do `CI Lead Time Analytics` com contrato `1.0.2`.

- Workflow run: `33692899180` (`#1154`)
- Commit medido: `cf467cd5e9fda039b4a5431aad1581cc49252aaa`
- Evento: `pull_request`
- Artifact: `ci-lead-time-analytics-33692899180`
- Artifact ID: `9870698698`
- SHA-256 do ZIP do artifact: `bebd83620a630eb6668bcd924796f6fbb20f2ff55e429ea723cac9639df001be`
- SHA-256 do `ci-lead-time-analytics.json`: `c4d51b56f48931c97320f21f42b3c0d3e39451ee418572d69e138206cd937df2`
- Snapshot versionado: `audit/baselines/ci-process-improvement-baseline-2026-09-02.json`

## Baseline observado

| Indicador | Valor |
|---|---:|
| Runs concluídos | 62 |
| Success rate | 77,42% |
| Failure rate | 6,45% |
| First-pass success | 77,42% |
| Rerun rate | 0,00% |
| Média | 18,89 s |
| P50 | 14,00 s |
| P90 | 33,60 s |
| P95 | 38,90 s |
| Máximo | 156,00 s |
| Desvio-padrão | 21,32 s |
| Coeficiente de variação | 112,91% |
| P95 de fila | 0,00 s |
| Throughput observado | 106,08 runs/h |

## Leitura inicial

O tempo de execução está baixo na janela observada, com P95 de 38,90 s, mas a variabilidade global ainda é alta (`CV=112,91%`). A taxa de falha observada foi 6,45% e a taxa de sucesso na primeira passagem foi 77,42%, portanto o snapshot permanece em `warning`.

Na comparação interna entre as duas metades da janela, P50 caiu 3 s, P95 caiu 38 s e CV caiu 65,01 pontos percentuais; a failure rate, porém, aumentou 6,45 pontos percentuais. Esses deltas são descritivos e não provam causalidade.

## Pareto de falhas

As quatro falhas observadas ficaram distribuídas igualmente entre quatro workflows, 25% cada:

1. `BACEN Non-Production Temporary Tolerance Guard`;
2. `PR CI Watch`;
3. `Teams Notification Control Center Smoke`;
4. `Teams Public Dashboard Smoke`.

Não existe, nesta amostra, uma única causa dominante que justifique um novo gate.

## Regra de uso

Este baseline é imutável. Comparações futuras devem usar este snapshot como referência, sem recalcular seus valores. Novas medições podem produzir novos snapshots, mas não devem sobrescrever este arquivo.

O baseline permanece `report-only`; ele não autoriza criação automática de thresholds, bloqueios de merge ou novos gates.
