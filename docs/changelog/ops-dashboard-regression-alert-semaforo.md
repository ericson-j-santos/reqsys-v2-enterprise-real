# Ops Dashboard — Regression Alert no Semáforo Executivo

## Resumo

Conecta o `runtime_executive_regression_alert` ao semáforo executivo principal do Ops Dashboard.

## Alterações

- Cria `scripts/inject_ops_dashboard_regression_alert_semaforo.py`.
- Cria `scripts/validate_ops_dashboard_regression_alert_semaforo.py`.
- Atualiza `.github/workflows/ops-dashboard.yml` para injetar e validar o semáforo temporal.

## Comportamento

O dashboard passa a exibir no topo:

- status do regression alert;
- risco temporal;
- produção bloqueada;
- quantidade de violations.

Quando `production_blocked=true`, o card principal `Status geral` é sobrescrito visualmente para `blocked`, preservando a rastreabilidade no drill-down.

## Guardrails

- Dashboard estático.
- Sem GitHub API em runtime.
- Sem secrets.
- Fallback seguro quando o artifact do regression alert ainda não existe.
- Validação offline/read-only.

## Próximo incremento seguro

Consolidar a evidência de bloqueio temporal no Executive Brief e no Runtime Executive Index como campo executivo de topo, permitindo consumo por outros painéis e gates externos.
