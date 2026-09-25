# Kubernetes + Argo CD — Bootstrap DEV

## Estado-alvo

A primeira etapa estabelece uma superfície GitOps mínima e segura:

    GitHub main
        |
        v
    Argo CD Application
        |
        v
    k8s/bootstrap/dev
        |
        v
    namespace reqsys-dev
        |
        v
    ConfigMap canário

O canário não contém segredo e não executa workload. O objetivo é provar a cadeia de reconciliação antes de colocar a API do ReqSys sob responsabilidade do cluster.

## Guardrails do primeiro ciclo

- somente ambiente development;
- namespace reqsys-dev;
- CreateNamespace=true;
- auto-sync ausente até o E2E real;
- Prune=confirm no recurso canário;
- nenhum Secret, Deployment, StatefulSet, DaemonSet, Job ou CronJob;
- nenhum deploy em STG/PROD;
- nenhuma dependência de runtime pago adicionada.

## Validação local/CI

    python scripts/validate_kubernetes_gitops_bootstrap.py
    python scripts/validate_kubernetes_gitops_bootstrap.py --self-test-negative
    python -m pytest tests/test_kubernetes_gitops_bootstrap.py -q

Esses comandos validam o contrato declarativo. Eles não provam que Argo CD ou Kubernetes estão ativos.

## E2E obrigatório antes de habilitar auto-sync

O E2E real deve usar o mesmo SHA e registrar um correlation_id:

1. cluster Kubernetes DEV acessível;
2. Argo CD instalado e saudável;
3. Application aplicada no namespace argocd;
4. sync manual concluído;
5. Argo CD reporta Synced e Healthy;
6. leitura independente via API Kubernetes confirma ConfigMap/reqsys-gitops-bootstrap em reqsys-dev;
7. o conteúdo observado contém environment=development e expected_namespace=reqsys-dev;
8. controle negativo comprova que namespace PROD e recursos sensíveis continuam bloqueados;
9. somente depois disso um incremento separado pode habilitar auto-sync em DEV.

## Próximo incremento

Depois do canário real, usar environment-observability-api como primeiro workload. A imagem já possui pipeline de build no GHCR e deve entrar no manifesto Kubernetes por referência imutável ghcr.io/...@sha256:<digest>, com probes de startup/readiness/liveness e contexto de segurança de pod/container.

O backend principal do ReqSys só entra depois que o piloto comprovar reconciliação, observabilidade e rollback no cluster DEV.
