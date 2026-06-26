# P1.3 — Git Provider Governed Adapters

**Status:** implementação inicial  
**Data:** 2026-06-25  
**Módulo:** ReqSys Agile Runtime  
**Decisão:** plano governado interno; execução externa fica para adaptadores autenticados futuros.

## 1. Objetivo

Materializar parcialmente as recomendações do Multi-IA Sprint Router em um plano GitOps auditável para GitHub/GitLab.

Esta fase não executa ações externas. Ela gera e registra planos governados para:

- issue;
- labels;
- branch;
- PR/MR;
- pipeline;
- evidência;
- aprovação humana quando risco alto.

## 2. Fluxo

```text
Work Item
→ Multi-IA Router
→ Git Provider Governed Plan
→ Preview
→ Registro como evidência
→ Aprovação humana quando necessário
→ Execução externa futura via adaptador autenticado
```

## 3. Endpoints

| Método | Rota | Uso |
|---|---|---|
| GET | `/v1/agile-runtime/work-items/{id}/git-provider/{provider}/plan` | Gera plano GitHub/GitLab sem efeito colateral |
| POST | `/v1/agile-runtime/work-items/{id}/git-provider/{provider}/register-plan` | Registra plano como evidência/auditoria |

`provider` pode ser:

```text
github
gitlab
```

## 4. Saída do plano

O plano retorna:

- provider;
- repository;
- issue title;
- issue body;
- labels;
- branch name;
- pipeline name;
- change kind (`pull_request` ou `merge_request`);
- governance mode;
- risk level;
- requires human approval;
- evidence title;
- evidence summary;
- next actions.

## 5. Segurança e limites

Esta fase não deve:

- usar token GitHub/GitLab;
- criar issue real;
- criar branch real;
- criar PR/MR real;
- disparar pipeline;
- fazer merge;
- fazer deploy.

A execução externa deve ser implementada em incremento posterior com:

- segredo via cofre;
- RBAC;
- auditoria;
- correlation_id;
- dry-run obrigatório;
- aprovação humana para risco alto;
- rollback operacional.

## 6. Critérios de aprovação humana

Aprovação humana é obrigatória quando:

- `score_risco >= 70`;
- owner IA é `security-ia`;
- owner IA é `devops-ia`;
- o plano envolver produção, deploy ou segurança.

## 7. Próximo incremento recomendado

P1.4 — Executor GitHub/GitLab em modo dry-run autenticado:

```text
plano registrado
→ validar credencial/cofre
→ dry-run de issue/labels/branch
→ salvar payload assinado
→ exigir aprovação
→ executar criação real
→ registrar URL e evidência
```

## 8. Métricas estimadas

| Dimensão | Antes | Após P1.3 | Alvo |
|---|---:|---:|---:|
| GitOps governado | 42% | 68% | 85% |
| Operação semi-autônoma | 58% | 68% | 80% |
| Rastreabilidade Story → PR/MR | 70% | 78% | 90% |
| Governança IA/Git | 82% | 86% | 92% |
