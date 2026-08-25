# Performance SLO, Error Budget e Degradação Sustentada

**Versão:** 1.0.0  
**Escopo:** performance pública do ReqSys  
**Política:** `config/runtime-performance-budgets.json`

## Objetivo

Complementar os budgets absolutos e o histórico 7/30 dias com uma decisão operacional que diferencie oscilação pontual de degradação sustentada.

O incremento não reduz nenhum budget absoluto existente. `Dynamic Performance Gate` continua sendo a fonte das medições e dos limites absolutos; `Performance SLO Error Budget Gate` consome a evidência histórica e decide SLO/error budget e streak.

## SLOs de performance

| SLO | Janela | Objetivo inicial |
|---|---:|---:|
| Latência API p95/p99 dentro do budget | 7 dias | 95% |
| Taxa de erro API dentro do budget | 7 dias | 99% |
| Throughput API acima do mínimo | 7 dias | 95% |
| Runtime browser dentro do budget | 7 dias | 95% |

O SLO só é considerado maduro após pelo menos 5 amostras. Antes disso o estado é `no_data`/`insufficient_history` e os budgets absolutos permanecem autoritativos.

## Error budget

Para um SLO com objetivo `T` e resultado observado `A`:

- budget total em pontos percentuais: `100 - T`;
- budget consumido: `max(0, 100 - A)`;
- budget restante em pontos percentuais: `A - T`;
- budget restante normalizado: `max(0, 100 - consumido / total * 100)`.

Quando o budget normalizado restante fica em até 25%, a decisão vira `watch`. Quando o resultado fica abaixo do objetivo, o SLO entra em `breach` e o gate strict bloqueia.

## Regressão relativa e streak

A regressão percentual continua usando os limites históricos já versionados:

- p95/p99: aumento acima de 30%;
- throughput: queda acima de 30%;
- error rate: aumento acima de 1 ponto percentual;
- métricas browser: aumento acima de 30%.

Uma regressão relativa isolada não bloqueia mais por si só: o relatório histórico mantém `status=passed` para compatibilidade de máquina e publica `decision=watch` como decisão operacional.

O bloqueio por tendência ocorre quando a mesma dimensão permanece além do limite por **3 execuções consecutivas**, comparada à mediana das amostras anteriores da janela de referência de 7 dias, com pelo menos 5 amostras de referência.

## Decisão final

| Situação | Decisão |
|---|---|
| Budget absoluto violado | bloqueia no Dynamic Performance Gate |
| Histórico ainda imaturo | não bloqueia por SLO relativo |
| 1 regressão relativa | `watch` |
| Error budget <= 25% restante | `watch` |
| SLO abaixo do objetivo | `blocked` |
| 3 degradações relativas consecutivas | `blocked` |
| Tudo conforme | `passed` |

## Fluxo

```text
ReqSys runtime
   ↓
Dynamic Performance Gate
   ↓
runtime-performance.json + browser-performance.json
   ↓
performance-history.json (7/30 dias)
   ↓
Performance SLO Error Budget Gate
   ↓
performance-slo-evidence.json
   ↓
passed | watch | insufficient_history | blocked
```

O workflow SLO é disparado após `Dynamic Performance Gate` em `main`, baixa o artifact `dynamic-performance-evidence-main`, calcula os SLOs, publica evidência por 45 dias e aplica fail-closed para ausência de evidência ou status inesperado.

## Alinhamento com observabilidade operacional

Os registros de SLO de performance usam os mesmos campos centrais do modelo operacional do ReqSys: `slo_id`, `name`, `environment`, `target_percent`, `window_days`, `actual_percent`, `error_budget_remaining`, `breach` e `status`.

Isso mantém compatibilidade conceitual com `generate_operational_slo_evidence.py` e com o Operational Observability Hub sem duplicar a definição genérica de SLO. A incorporação visual dessa nova evidência no painel administrativo é o próximo incremento de UX/Operação.

## Guardrails

- budgets absolutos não são afrouxados;
- apenas medições de `main` formam baseline produtivo;
- PR permanece advisory para runtime externo;
- nenhuma mutação de produção é feita pelo avaliador;
- correlation ID identifica a execução SLO;
- evidência é persistida em artifact por 45 dias;
- parâmetros só devem ser recalibrados com histórico suficiente e justificativa registrada.
