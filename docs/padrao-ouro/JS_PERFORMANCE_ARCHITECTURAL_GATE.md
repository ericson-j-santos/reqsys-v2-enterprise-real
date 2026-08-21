# JS Performance Architectural Gate

**Versão:** 1.1.0  
**Escopo:** JavaScript, TypeScript, Vue e runtime público ReqSys  
**Modo:** estático em PR + dinâmico pós-deploy

## Objetivo

Impedir que novos padrões de alto risco de performance entrem no código e detectar regressões reais de runtime por evidência mensurável, sem transformar heurísticas em bloqueios indiscriminados.

A solução combina:

1. gate estático incremental por diff;
2. orçamento HTTP por endpoint com p95/p99, throughput e taxa de erro;
3. probe Chromium para event-loop lag, Long Tasks, LCP, heap e GC;
4. OpenTelemetry para distribuição de duração e volume HTTP;
5. pipeline OTLP de métricas no collector existente.

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
- violações do orçamento.

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

Execução:

```bash
node frontend/scripts/browser-performance-gate.mjs \
  --url https://reqsys-app.fly.dev \
  --budgets config/runtime-performance-budgets.json \
  --output artifacts/performance/browser-performance.json \
  --strict
```

## OpenTelemetry

O backend existente foi preservado e ampliado. Quando `OTEL_ENABLED=true`:

- traces continuam sendo exportados via OTLP/HTTP;
- métricas passam a ser exportadas para `/v1/metrics`;
- `reqsys.http.server.requests` registra volume por método, route template e status;
- `reqsys.http.server.duration` registra distribuição de duração em milissegundos;
- route templates são usados para evitar cardinalidade por IDs reais;
- correlation ID continua no span, não em atributos de resource.

O collector `services/environment-observability-api/collector/config.yaml` possui pipelines separados de `traces` e `metrics`, ambos com memory limiter, resource processor, batch, queue/retry e exporter governado já existente.

## Política de execução no CI

Workflow: `Dynamic Performance Gate`.

| Contexto | Modo | Decisão |
|---|---|---|
| Pull Request | advisory | coleta baseline sem bloquear por instabilidade externa |
| `workflow_dispatch` | configurável | strict por padrão |
| pós-deploy `ReqSys Fly Runtime P0` | strict | bloqueia orçamento violado |
| schedule diário | advisory | histórico/baseline |

Isso evita acoplar merge de código à disponibilidade momentânea do Fly, mas torna a regressão impeditiva no caminho pós-deploy.

## Evidências

Artifacts:

- `js-performance-gate-evidence/report.json`;
- `dynamic-performance-evidence/runtime-performance.json`;
- `dynamic-performance-evidence/browser-performance.json`.

Retenção do gate dinâmico: 30 dias.

## Exceção governada do gate estático

Uma ocorrência pode ser suprimida apenas localmente, com regra explícita e justificativa não trivial:

```javascript
// performance-gate: allow PERF001 reason=bootstrap executa antes de aceitar trafego
const config = readFileSync('config.json', 'utf8')
```

A supressão fica registrada no relatório JSON e não remove a evidência.

## Decisão operacional

- estático `blocked`: CI falha;
- dinâmico PR: mede e evidencia, sem penalizar transient externo;
- dinâmico pós-deploy `blocked`: deployment não atende ao orçamento e requer investigação/correção;
- orçamento só deve ser alterado com evidência histórica e justificativa, nunca apenas para tornar o gate verde.

## Próximo incremento

Consolidar a série histórica dos artifacts em dashboard de performance e calibrar budgets por baseline de 7/30 dias, com alerta de regressão percentual além do limite absoluto.
