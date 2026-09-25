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

## E2E real sem depender do host físico

O workflow CI E2E Governado possui uma rota específica para o escopo Kubernetes/GitOps. Ela cria um cluster kind efêmero no runner, instala Argo CD v3.5.3 a partir do commit imutável c9c369efcc5b2a0bd720803f8d14a1c3eaddf579, aplica a Application e dispara uma sincronização manual no SHA exato avaliado.

O aceite exige simultaneamente:

- Application com auto-sync ausente;
- status Argo CD Synced e Healthy;
- status.sync.revision igual ao SHA avaliado;
- operação de sync Succeeded;
- leitura independente de ConfigMap/reqsys-gitops-bootstrap em reqsys-dev;
- environment=development, expected_namespace=reqsys-dev e purpose=gitops-bootstrap-canary;
- zero Deployment, StatefulSet, DaemonSet, Job ou CronJob no namespace;
- controle negativo do validador aprovado;
- artifact artifacts/kubernetes-gitops-e2e/evidence.json ligado a SHA e correlation_id;
- cluster kind removido ao final, inclusive em falha.

Esse E2E comprova a cadeia declarativa em Kubernetes real. Ele não transforma o runner do GitHub em runtime persistente. O destino persistente continua sendo o PC24x7 Desktop, condicionado à recuperação do bootstrap host-side e do Command Gateway.

## Disparo pós-merge sem interface manual

O merge governado pode ser criado por um workflow com `GITHUB_TOKEN`; nesse caso, o GitHub não dispara outro workflow por `push` recursivo. Para produzir a evidência pós-merge no SHA real de `main`, usar o comando exato na issue operacional #1705:

    /reqsys run kubernetes-argocd-e2e-dev

O Authorized Actions Gateway captura o SHA corrente de `main`, despacha somente `ci-e2e-governado.yml` por `workflow_dispatch` e valida `run_id`, URL, `headSha` e evento antes de registrar a evidência sanitizada. Nenhum parâmetro arbitrário é aceito e a rota usa runner GitHub-hosted, sem depender do PC24x7.
