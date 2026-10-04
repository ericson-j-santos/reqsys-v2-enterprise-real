# CI Enterprise Continuous Maturity — ReqSys

## Objetivo

Manter a esteira rápida, determinística, auditável e com regressão/observabilidade separadas do caminho crítico.

## Superfícies canônicas

| Função | Arquivo/workflow atual |
|---|---|
| Prontidão antes de CI caro | `.github/workflows/pre-pr-readiness.yml` |
| Fast path obrigatório | `.github/workflows/ci-enterprise-fast.yml` |
| CI principal | `.github/workflows/ci.yml` |
| Regressão ampla | `.github/workflows/ci-enterprise-regression.yml` |
| Observabilidade | `.github/workflows/ci-observability.yml` |
| Guardrails determinísticos | `scripts/ci_enterprise_guardrails.py` |
| Política de merge no SHA atual | `governance/merge/current-sha-required-workflows.json` |
| Fila de merge governada | `.github/workflows/governed-merge-queue.yml` |

## Fluxo operacional

1. O Pre-PR valida o HEAD e a base atuais.
2. O CI Enterprise Fast executa admission controller e guardrails antes do trabalho mais caro.
3. O CI principal executa os jobs aplicáveis ao perfil da mudança.
4. A regressão enterprise roda fora do caminho crítico por agenda/manual e registra resultado como evidência.
5. CI Observability recebe eventos dos workflows canônicos e publica painel operacional.
6. Governed Merge Queue revalida estabilidade, mergeabilidade e workflows obrigatórios no SHA atual.

## Política de falha

- **Falha determinística:** corrigir a menor causa raiz no mesmo PR e executar novamente no novo SHA.
- **Flaky confirmado:** registrar ocorrência, isolar causa e adicionar prevenção; rerun é mitigação, não solução.
- **Workflow pendente:** não criar commit sem relação.
- **SHA mudou:** invalidar evidência anterior.
- **Base avançou:** sincronizar preservando o trabalho e repetir checks.

## Política de regressão

`CI Enterprise Regression` é deliberadamente report-only em etapas de regressão ampla quando indicado pelo próprio artifact. Ele não substitui os workflows obrigatórios de PR.

## Indicadores

- tempo até primeira falha;
- tempo até verde;
- flaky rate;
- reruns sem mudança;
- divergência de SHA;
- falhas recorrentes sem prevenção.

Metas são tendências operacionais, não motivo para ocultar falhas reais.

## Anti-duplicação

Não criar novamente `ci-enterprise-observability.yml` ou outra esteira equivalente enquanto `CI Observability` for a superfície canônica registrada. Mudanças devem evoluir a superfície atual ou seus contratos, não multiplicar workflows.
