# P1.2 — Multi-IA Sprint Router

**Status:** implementação inicial  
**Data:** 2026-06-25  
**Módulo:** ReqSys Agile Runtime  
**Decisão:** manter como módulo interno do `reqsys-v2-enterprise-real`.

## 1. Objetivo

Adicionar uma camada operacional para sugerir automaticamente qual IA/agente deve assumir um work item do Agile Runtime.

O roteador não executa GitHub/GitLab diretamente nesta fase. Ele apenas recomenda e registra:

- IA destino;
- categoria operacional;
- labels sugeridas;
- branch sugerida;
- pipeline sugerido;
- prioridade sugerida;
- confiança;
- justificativas;
- ações recomendadas.

## 2. Fluxo

```text
Work Item
→ Multi-IA Sprint Router
→ Preview sem efeito colateral
→ Aplicação governada
→ owner_ai + branch + prioridade
→ evidência auditável
```

## 3. Endpoints

| Método | Rota | Uso |
|---|---|---|
| GET | `/v1/agile-runtime/work-items/{id}/ai-routing/preview` | Simula recomendação sem alterar o item |
| POST | `/v1/agile-runtime/work-items/{id}/ai-routing/apply` | Aplica owner IA, prioridade, branch e evidência |

## 4. IAs destino

| IA | Critérios principais | Pipeline sugerido |
|---|---|---|
| `security-ia` | segurança, LGPD, JWT, token, secret, auth, CORS | `security-governance-gates` |
| `devops-ia` | CI/CD, GitHub, GitLab, deploy, Docker, Fly, workflow | `ci-cd-pipeline` |
| `backend-ia` | API, FastAPI, SQLAlchemy, Pydantic, banco, backend | `backend-ci` |
| `frontend-ia` | UI, UX, Vue, Vite, Vuetify, Kanban, dashboard | `frontend-ci` |
| `qa-ia` | pytest, coverage, evidência, validação, regressão | `quality-gates` |
| `arquiteto-ia` | ADR, arquitetura, domínio, governança, runtime | `architecture-review` |
| `analista-requisitos-ia` | requisito, story, critérios, Gherkin, DoR, DoD | `requirements-review` |

## 5. Limites desta fase

O P1.2 inicial não deve:

- criar issue automaticamente;
- criar branch remotamente;
- acionar pipeline externo;
- aplicar label no GitHub/GitLab;
- fazer merge;
- executar deploy;
- substituir revisão humana em risco alto.

Essas ações devem entrar em fase posterior como adaptadores governados.

## 6. Critérios de segurança

- Risco alto recomenda revisão humana obrigatória.
- Integrações externas devem ficar fora do domínio, via adaptadores.
- A aplicação do roteamento registra evidência e auditoria.
- Não há uso de segredo ou token nesta fase.

## 7. Próximo incremento recomendado

P1.3 — Adaptadores governados GitHub/GitLab para materializar a recomendação:

```text
routing aplicado
→ criar/atualizar issue
→ aplicar labels
→ sugerir branch
→ mapear PR/MR
→ acompanhar CI
→ registrar evidência
```

## 8. Métricas esperadas

| Dimensão | Antes | Após P1.2 | Alvo |
|---|---:|---:|---:|
| Multi-IA operacional | 40% | 65% | 85% |
| Roteamento de stories | 35% | 70% | 90% |
| Governança IA | 76% | 82% | 90% |
| Operação semi-autônoma | 45% | 58% | 80% |
