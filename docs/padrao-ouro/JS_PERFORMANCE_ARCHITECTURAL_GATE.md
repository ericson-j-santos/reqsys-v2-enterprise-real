# JS Performance Architectural Gate

**Versão:** 1.0.0  
**Escopo:** JavaScript, TypeScript e Vue  
**Modo padrão:** incremental por diff de Pull Request

## Objetivo

Impedir que novos padrões de alto risco de performance entrem no código de runtime sem transformar recomendações heurísticas em bloqueios indiscriminados.

O gate segue abordagem fail-closed para operações síncronas que podem bloquear o event loop em código de aplicação e modo advisory para sinais que dependem de volume ou contexto de execução.

## Regras

| Regra | Severidade em runtime | Critério | Decisão |
|---|---|---|---|
| `PERF001` | erro | APIs síncronas de filesystem | bloqueia |
| `PERF002` | erro | `child_process` síncrono | bloqueia |
| `PERF003` | erro | operações criptográficas síncronas de custo relevante | bloqueia |
| `PERF004` | warning | cadeias `map/filter/flatMap/reduce` | revisão |
| `PERF005` | warning | excesso de `console.log/debug/info` | revisão |
| `PERF006` | erro | operação síncrona em/próxima de handler HTTP | bloqueia |
| `PERF007` | warning | handler combina loop e transformação de coleção | revisão |

Fora de caminhos de runtime, regras `PERF001` a `PERF003` são advisory. Isso preserva usos legítimos em build, configuração e automação sem permitir o mesmo padrão no caminho crítico da aplicação.

## Caminhos de runtime

Por padrão:

- `frontend/src/`
- `src/`
- `app/`
- `server/`
- `services/`
- `packages/`

Testes, fixtures, exemplos, dependências e artefatos de build são excluídos.

## Execução

Somente alterações do PR:

```bash
python scripts/js_performance_gate.py --base-ref origin/main
```

Varredura completa:

```bash
python scripts/js_performance_gate.py --all
```

Arquivos específicos:

```bash
python scripts/js_performance_gate.py --paths frontend/src/main.js frontend/src/services/api.js
```

## Exceção governada

Uma ocorrência pode ser suprimida apenas localmente, com regra explícita e justificativa não trivial:

```javascript
// performance-gate: allow PERF001 reason=bootstrap executa antes de aceitar trafego
const config = readFileSync('config.json', 'utf8')
```

A supressão fica registrada no relatório JSON e não remove a evidência.

## Evidência

O workflow `JS Performance Architectural Gate` gera o artifact:

`js-performance-gate-evidence/report.json`

Campos principais:

- `scanned_files`
- `blockers`
- `warnings`
- `suppressed`
- `status`
- lista de achados com regra, arquivo, linha, evidência e justificativa da supressão

## Decisão operacional

- `status=blocked`: CI falha; a causa deve ser corrigida ou excepcionalmente justificada.
- `status=passed` com warnings: CI passa, mas o Pull Request mantém evidência para revisão.
- falha ao calcular o diff: o scanner retorna código `2`; o workflow falha em vez de assumir sucesso.

## Próximo incremento

Após estabilização do gate estático, incorporar métricas de runtime e carga: event-loop lag, p95/p99, heap/GC, throughput, OpenTelemetry e orçamento de performance por endpoint.
