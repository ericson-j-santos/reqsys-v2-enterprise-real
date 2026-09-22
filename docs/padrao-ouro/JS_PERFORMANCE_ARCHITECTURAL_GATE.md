# JS Performance Architectural Gate

**Versão:** 1.2.0  
**Escopo:** JavaScript, TypeScript, Vue e runtime público ReqSys  
**Modo:** estático em PR + dinâmico pós-deploy + baseline histórico 7/30 dias

## Objetivo

Impedir que novos padrões de alto risco de performance entrem no código e detectar regressões reais de runtime por evidência mensurável, sem transformar heurísticas em bloqueios indiscriminados.

A solução combina:

1. gate estático incremental por diff;
2. orçamento HTTP por endpoint com p95/p99, throughput e taxa de erro;
3. probe Chromium para event-loop lag, Long Tasks, LCP, heap e GC;
4. OpenTelemetry para distribuição de duração e volume HTTP;
5. pipeline OTLP de métricas no collector existente;
6. série rolling 7/30 dias baseada em artifacts do lane `main`;
7. detecção percentual contra mediana histórica;
8. dashboard HTML autocontido por execução.

## Gate estático

| Regra | Severidade em runtime | Critério | Decisão |
|---|---|---|---|
| `PERF001` | erro | APIs síncronas de filesystem | bloqueia |
| `PERF002` | erro | `child_process` síncrono | bloqueia |
| `PERF003` | erro | operações criptográficas síncronas de custo relevante | bloqueia |
| `PERF004` | warning | cadeias `map/filter/flatMap/reduce` | revisão |
| `PERF005` | warning | excesso de `console.log/debug/info` | revisão |
| `PERF006` | erro | operação síncrona em/próxima de handler HTTP | bloqueia |
| `PERF007` | warning | handler combina loop e transformação de coleção | revisão |

Fora de caminhos de runtime, regras `PERF001` a `PERF003` são advisory. Testes, fixtures, exemplos, dependências e artefatos de build são excluídos.

### Execução estática

```bash
python scripts/js_performance_gate.py --base-ref origin/main
python scripts/js_performance_gate.py --all
```

## Gate dinâmico HTTP

Política versionada: `config/runtime-performance-budgets.json`.

O `scripts/runtime_performance_gate.py` executa warm-up controlado e amostras concorrentes somente em endpoints `GET`, com `X-Correlation-Id`, timeout e volume limitado.

Métricas por endpoint:

- p50;
- p95;
- p99;
- média e máximo;
- throughput em req/s;
- taxa de erro;
- violações do orçamento absoluto.

Execução:

```bash
python scripts/runtime_performance_gate.py \
  --base-url https://reqsys-api.fly.dev \
  --budgets config/runtime-performance-budgets.json \
  --output artifacts/performance/runtime-performance.json \
  --strict
```

O gate recusa métodos mutáveis (`POST`, `PUT`, `PATCH`, `DELETE`) para impedir carga sintética com efeito colateral em produção.

## Gate dinâmico JavaScript no browser

O `frontend/scripts/browser-performance-gate.mjs` executa o frontend em Chromium e mede:

- `event_loop_lag_p95_ms`;
- `event_loop_lag_max_ms`;
- quantidade e duração máxima de Long Tasks;
- LCP;
- heap antes e depois de GC;
- memória recuperada pelo GC;
- round-trip da coleta de GC.

## Série histórica 7/30 dias

O `scripts/performance_history.py` fecha a lacuna entre orçamento absoluto e regressão relativa.

### Persistência

A persistência é rolling e auditável via GitHub Actions artifact:

`dynamic-performance-evidence-main`

Cada execução do lane `main`:

1. recupera o artifact histórico `main` mais recente;
2. lê `performance-history.json`;
3. incorpora a medição atual;
4. remove duplicidades;
5. poda amostras fora da retenção configurada;
6. recalcula baseline 7d e 30d;
7. publica novamente o histórico consolidado e o dashboard.

A retenção foi configurada em **45 dias**, suficiente para sustentar a janela móvel de 30 dias sem escrever diretamente no branch protegido.

Medições de Pull Request **não entram no baseline**. PRs podem comparar a medição corrente com o baseline de `main`, mas publicam em artifact separado:

`dynamic-performance-evidence-pr`

Isso evita contaminar produção com medições de branches.

### Baseline

O baseline usa a **mediana** das amostras anteriores, excluindo a medição atual.

A regressão relativa só se torna madura após atingir:

`minimum_baseline_samples = 5`

Enquanto houver menos amostras, o estado é:

`insufficient_history`

Esse estado não bloqueia pós-deploy; budgets absolutos continuam sendo aplicados normalmente.

### Limites relativos iniciais

| Métrica | Regra de regressão |
|---|---:|
| p95 / p99 | aumento > 30% |
| throughput | queda > 30% |
| taxa de erro | aumento > 1 ponto percentual |
| métricas browser selecionadas | aumento > 30% |

Os limites ficam versionados em `config/runtime-performance-budgets.json`.

Uma regressão pode bloquear mesmo quando o valor ainda está dentro do teto absoluto. Isso detecta degradação gradual antes de atingir um limite crítico.

## Dashboard de performance

Cada execução produz:

`performance-dashboard.html`

O HTML é autocontido, sem dependências externas, e apresenta:

- semáforo do gate histórico;
- quantidade de amostras rolling;
- maturidade 7d e 30d;
- regressões detectadas;
- p95 atual × mediana 7d × mediana 30d;
- throughput e taxa de erro;
- métricas de runtime JavaScript;
- tendência p95 em sparkline SVG;
- tabela detalhada das regressões maduras.

O dashboard fica dentro do mesmo artifact da evidência dinâmica.

## OpenTelemetry

Quando `OTEL_ENABLED=true`:

- traces continuam sendo exportados via OTLP/HTTP;
- métricas são exportadas para `/v1/metrics`;
- `reqsys.http.server.requests` registra volume por método, route template e status;
- `reqsys.http.server.duration` registra distribuição de duração em milissegundos;
- route templates evitam cardinalidade por IDs reais;
- correlation ID continua no span, não em atributos de resource.

O collector possui pipelines separados de `traces` e `metrics`, ambos com memory limiter, resource processor, batch, queue/retry e exporter governado.

## Política de execução no CI

Workflow: `Dynamic Performance Gate`.

| Contexto | Lane | Modo | Decisão |
|---|---|---|---|
| Pull Request | `pr` | advisory | mede e compara, sem contaminar baseline |
| `workflow_dispatch` em `main` | `main` | strict por padrão | budget absoluto + regressão madura |
| `workflow_dispatch` fora de `main` | `pr` | strict configurável | não persiste no baseline main |
| pós-deploy `ReqSys Fly Runtime P0` | `main` | strict | bloqueia orçamento ou regressão madura |
| schedule diário | `main` | advisory | alimenta histórico/baseline |

## Evidências

Artifacts principais:

- `js-performance-gate-evidence/report.json`;
- `dynamic-performance-evidence-main/runtime-performance.json`;
- `dynamic-performance-evidence-main/browser-performance.json`;
- `dynamic-performance-evidence-main/performance-history.json`;
- `dynamic-performance-evidence-main/performance-dashboard.html`.

Retenção do gate dinâmico: **45 dias**.

## Decisão operacional

- estático `blocked`: CI falha;
- dinâmico PR: mede e evidencia, sem penalizar transient externo;
- histórico `insufficient_history`: não bloqueia, pois ainda não há amostra suficiente;
- histórico `blocked`: regressão percentual madura detectada;
- pós-deploy strict: exige budgets absolutos conformes e histórico não bloqueado;
- orçamento só deve ser alterado com evidência histórica e justificativa, nunca apenas para tornar o gate verde.

## Próximo incremento

Após formar baseline real suficiente, incorporar SLO/error budget e alertas de tendência consecutiva para diferenciar regressão pontual de degradação sustentada.
