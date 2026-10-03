# Copilot Studio Multiagente — ReqSys Low-Code

Data: 2026-07-12  
Status: implementação P0 governada; provisionamento real no tenant permanece pendente.

## Objetivo

Materializar o blueprint conceitual do LowCode Solution Factory como uma solução multiagente consumível pelo Copilot Studio, com geração determinística de tópicos `.mcs.yml`, contratos de workflows Power Automate, RBAC e pacote ZIP.

## Componentes

- **Orquestrador:** classifica a intenção e realiza handoff; não executa escrita externa.
- **Agente de Demandas:** cria e consulta demandas.
- **Agente de Aprovações:** prepara contexto; não substitui decisão humana.
- **Agente de Releases:** consolida evidências e recomenda go/no-go; não promove release.
- **Factory:** `backend/app/services/copilot_studio_factory.py`.
- **Schema:** `backend/app/schemas/copilot_studio_solution.py`.
- **API:** `POST /v1/hub-lowcode/copilot-studio/generate` e `POST /v1/hub-lowcode/copilot-studio/generate/canvas`.

## Guardrails

1. Autonomia N1 assistiva.
2. Confirmação humana antes de operações de escrita.
3. RBAC por security role do Dataverse.
4. `correlation_id` obrigatório em todos os workflows.
5. Idempotência por `correlation_id`.
6. DEV → STG → PROD, com aprovação e rollback.
7. Nenhuma aprovação, publicação ou promoção automática.

## Pacote gerado

A resposta da factory contém `package.zip_base64` e inventário de arquivos. O ZIP inclui:

- `CANVAS.md`;
- `manifest.json`;
- `alm/package-plan.json`;
- agentes e tópicos em `copilot-workspace/`;
- `security/security-mapping.json`;
- `workflows/flows.json`.

## Limites atuais

O P0 gera artefatos e contratos, mas não provisiona diretamente componentes no tenant Microsoft. A materialização real exige conexão autenticada, referências de conexão, importação ALM e validação em DEV/STG/PROD.

## Validação

```bash
cd backend
python -m pytest tests/test_copilot_studio_factory.py tests/test_copilot_studio_api_critical_paths.py -q
```
