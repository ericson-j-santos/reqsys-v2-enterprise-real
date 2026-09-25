# Kubernetes + Argo CD DEV Bootstrap — Requisitos

## Objetivo

Criar a primeira superfície GitOps executável do ReqSys para Kubernetes e Argo CD sem confundir configuração declarativa com evidência de runtime.

## Escopo

O incremento cobre somente development. Ele não provisiona cluster, não instala Argo CD, não publica segredos e não promove STG/PROD. O primeiro recurso sincronizável é um ConfigMap canário sem dados sensíveis.

## Requisitos

1. A aplicação Argo CD deve ler main do repositório canônico e apontar somente para k8s/bootstrap/dev.
2. O destino Kubernetes deve ser https://kubernetes.default.svc e o namespace reqsys-dev.
3. O namespace pode ser criado pelo Argo CD via CreateNamespace=true.
4. Auto-sync deve permanecer ausente até o E2E real Git -> Argo CD -> Kubernetes ser comprovado.
5. O bootstrap deve conter somente um ConfigMap canário e proibir Secret e workloads.
6. Exclusão do canário deve exigir confirmação de prune.
7. O validador deve ser determinístico, idempotente e falhar fechado.

## Critérios de aceite (Acceptance Criteria)

1. python scripts/validate_kubernetes_gitops_bootstrap.py retorna status=passed.
2. python scripts/validate_kubernetes_gitops_bootstrap.py --self-test-negative comprova que auto-sync precoce, Secret e namespace PROD são rejeitados.
3. python -m pytest tests/test_kubernetes_gitops_bootstrap.py -q aprova casos positivos, negativos e idempotência.
4. O Pre-PR Readiness Gate retorna READY_FOR_PR=passed no HEAD exato e behind_by=0 antes da abertura da PR.
5. Nenhum deploy, instalação de cluster, segredo, STG ou PROD é executado neste incremento.
6. O E2E de runtime só pode ser declarado concluído após leitura independente no cluster confirmar o ConfigMap criado pelo Argo CD no mesmo commit.
