# Executive Predictive Stability CI

## Objetivo

Executar a camada `Executive Predictive Stability Layer` de forma governada no CI, publicando artifacts executivos sem deploy, sem escrita externa e sem mutação produtiva.

## Workflow

```text
.github/workflows/executive-predictive-stability.yml
```

## Segurança

- `permissions: contents: read`.
- Sem secrets adicionais.
- Sem auto-commit.
- Sem deploy.
- Sem escrita externa.
- Sem chamada a IA externa.
- Retenção de artifacts por 90 dias.

## Artifacts publicados

```text
artifacts/executive-predictive-stability/
├── executive-predictive-stability.json
├── executive-predictive-stability.html
└── summary.md
```

## Critérios de aceite

- Workflow executa em PR quando arquivos relevantes mudam.
- Workflow pode ser acionado por `workflow_dispatch`.
- Artifacts executivos são publicados.
- Execução falha se confiança ficar abaixo do limite configurado.
- Execução falha se risco previsto ultrapassar o limite configurado.

## Próximo incremento recomendado

Integrar o artifact `executive-predictive-stability.json` ao dashboard executivo vivo do ReqSys para drill-down temporal de risco, confiança e degradação por workflow.
