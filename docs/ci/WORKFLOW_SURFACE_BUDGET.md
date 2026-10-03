# Workflow Surface Budget

Objetivo: impedir que a superfície de GitHub Actions continue crescendo enquanto o caminho crítico de entrega é consolidado.

## Política

- O número líquido de arquivos em `.github/workflows` não pode aumentar em uma mudança.
- Um workflow novo que substitua outro deve permanecer com saldo líquido zero ou negativo.
- Um workflow novo com gatilho `pull_request` amplo só é permitido quando faz parte do caminho canônico declarado em `config/workflow-governance-registry.json`.
- Workflows informativos devem preferir `paths`, `workflow_run`, `schedule` ou `workflow_dispatch`.
- O controle é executado no `Pre-PR Readiness Gate`; falha bloqueia `READY_FOR_PR`.

## Caminho canônico de PR

1. Pre-PR Readiness Gate
2. ReqSys Required Fast Gate
3. CI — ReqSys v2 Enterprise / CI Enterprise Fast
4. Security Specialized Scanners
5. PR Evidence Gate
6. PR Conflict Guard
7. Governed Merge Queue

Este incremento congela a proliferação. A redução dos workflows existentes deve ocorrer por substituição/consolidação mensurável, preservando evidência e gates obrigatórios.
