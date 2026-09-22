# ReqSys Operational Orchestrator v1

## Objetivo

Transformar o Actions Runtime Center em uma cadeia operacional rastreável:

`fonte -> Action Queue -> Decision Gate -> executor governado -> Evidence Ledger -> próxima ação`.

A implementação v1 consolida três incrementos: Action Queue, Readiness as Code e Evidence Ledger. O executor automático é deliberadamente restrito a operações verdes explicitamente permitidas. Alterações de código/CI entram como risco amarelo e exigem aprovação/executor externo governado.

## Estado evidenciado x alvo

| Capacidade | Estado v1 | Alvo evolutivo |
| --- | --- | --- |
| Action Queue | SQLite, idempotente, estados e tentativas persistidos | adaptador de persistência durável gerenciada quando necessário |
| Decision Gate | green/yellow/red; allowlist de executor automático | políticas por domínio e ambiente |
| Readiness as Code | manifesto DEV versionado, referências sem valores | probes reais por conector/ambiente |
| Evidence Ledger | SQLite append-only, vinculado a SHA/correlation_id | exportação para storage durável/auditoria |
| Executor governado | `readiness_check` automático; demais falham fechado | adaptadores GitHub/GitLab/Power Platform/terminal pelo executor autorizado |
| GitHub Actions | falha terminal vira ação amarela | ingestão automática via webhook autenticado/evento interno |

## Persistência

Por padrão, o banco SQLite é criado no diretório temporário do sistema operacional. Para persistência durável, configure somente o caminho, sem segredo:

`REQSYS_OPERATIONAL_DB_PATH=/caminho/volume/state.sqlite3`

O schema possui duas estruturas:

- `actions`: fila idempotente, status, risco, executor, branch, SHA e `correlation_id`;
- `evidence`: ledger append-only. A implementação não expõe operações de update/delete de evidência.

## Readiness as Code

Manifesto canônico DEV: `config/operational-orchestrator/dev.yaml`.

O arquivo usa sintaxe JSON, que é YAML 1.2 válido, para não adicionar dependência obrigatória a PyYAML. Nenhum valor de credencial deve ser gravado no manifesto. Somente nomes de referências são permitidos.

Referências esperadas no DEV:

| Capacidade | Referências |
| --- | --- |
| Excel | `REQSYS_EXCEL_WORKBOOK_ID`, `REQSYS_EXCEL_TABLE_NAME` |
| SQL Server | `REQSYS_SQL_SERVER_HOST`, `REQSYS_SQL_SERVER_DATABASE` |
| SharePoint | `REQSYS_SHAREPOINT_SITE_ID`, `REQSYS_SHAREPOINT_LIST_ID` |
| Power Automate | `REQSYS_POWER_AUTOMATE_FLOW_ID` |
| Planner | `REQSYS_PLANNER_PLAN_ID` |
| Teams | `REQSYS_TEAMS_TEAM_ID`, `REQSYS_TEAMS_CHANNEL_ID` |
| Identidade Microsoft | `REQSYS_MSAL_TENANT_ID`, `REQSYS_MSAL_CLIENT_ID` |

Credenciais, tokens, client secrets e senhas permanecem no cofre/provedor de identidade e nunca são copiados para a evidência.

## Decision Gate

- `green`: pode executar automaticamente somente se o executor estiver na allowlist interna.
- `yellow`: exige confirmação e executor externo governado; não há fallback para terminal irrestrito.
- `red`: ação humana obrigatória; o serviço falha fechado.

Na v1, a allowlist contém somente `readiness_check`. Uma falha de CI é classificada como `yellow`, com executor `github_agent`; portanto, o ReqSys registra a pendência, mas não altera código autonomamente sem executor autorizado.

## API

A API existente `/v1/actions-runtime` foi estendida com:

- `GET /orchestrator/status`
- `GET /orchestrator/readiness`
- `GET /orchestrator/actions`
- `GET /orchestrator/evidence`
- `POST /orchestrator/cycle`
- `POST /orchestrator/actions/{action_id}/execute`
- `POST /orchestrator/ingest/workflow-run`

As rotas do orquestrador exigem administrador.

## Fluxo E2E v1

```text
manifesto + SHA atual
        |
        v
Action Queue
        |
        v
Decision Gate (green)
        |
        v
readiness_check
        |
        +---- blocked -> Evidence Ledger
        |
        +---- ready ---> Evidence Ledger
                              |
                              v
                    leitura SQLite independente
```

## Controles contra falso positivo

`scripts/validate_operational_orchestrator_e2e.py` cria armazenamento temporário novo e executa:

1. caso positivo com `correlation_id` único e SHA conhecido;
2. leitura independente do SQLite para confirmar a evidência persistida;
3. repetição idempotente da mesma entrada, comprovando uma única ação/evidência;
4. caso negativo com referência obrigatória ausente;
5. teste do próprio teste consultando o `correlation_id` correto com SHA deliberadamente incorreto e exigindo zero registros.

O workflow `Operational Orchestrator CI` executa compilação, validação do manifesto/schema, testes do núcleo e esse E2E.

## Critério de conclusão do incremento

A v1 somente pode ser considerada validada no SHA corrente quando:

- o workflow dedicado executar e ficar verde no SHA da PR;
- os checks gerais aplicáveis da PR estiverem aprovados;
- o E2E dedicado reportar positivo, negativo, leitura independente, idempotência e controle de falso positivo;
- nenhum valor secreto aparecer em manifesto, saída ou Evidence Ledger;
- mergeabilidade e concorrência forem revalidadas no SHA final.

O merge continua fora do escopo sem autorização explícita.
