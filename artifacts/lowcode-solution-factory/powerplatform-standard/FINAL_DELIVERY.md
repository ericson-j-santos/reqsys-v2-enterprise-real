# ReqSysLowCode Materialized Delivery

Data: 2026-07-02  
Ambiente materializado: `tieri (default)`  
URL: `https://orga258f260.crm2.dynamics.com/`

## Solutions exportadas do ambiente

| Arquivo | Conteudo | Uso |
| --- | --- | --- |
| `ReqSysLowCode_materialized_unmanaged.zip` | Solution principal com tabelas Dataverse, colunas, security roles e web resources de blueprint | DEV/sandbox |
| `ReqSysLowCode_materialized_managed.zip` | Versao managed da solution principal | Promocao controlada |
| `ReqSysLowCode_materialized_connector_unmanaged.zip` | Solution principal com Dataverse, roles, web resources e custom connector nativo | DEV/sandbox |
| `ReqSysLowCode_materialized_connector_managed.zip` | Versao managed com custom connector | Promocao controlada |
| `ReqSysLowCodeCopilot_unmanaged.zip` | Copilot Studio agent nativo `reqsys_ReqSysLowCodeCopilot` | DEV/sandbox |
| `ReqSysLowCodeCopilot_managed.zip` | Versao managed do Copilot | Promocao controlada |
| `ReqSysLowCodeCanvas.msapp` | Canvas App gerado via custom connector `ReqSysLowCodeConnector` | Importar/abrir no Power Apps Studio |

## Componentes nativos criados

### Dataverse

Tabelas criadas na solution `ReqSysLowCode`:

- `reqsys_demanda`
- `reqsys_requisito`
- `reqsys_aprovacao`
- `reqsys_evidencia`
- `reqsys_release`

Colunas principais criadas conforme `materialization-evidence.json`. Lookups foram marcados como `skipped_lookup_p0` para evitar relacionamento inconsistente nesta primeira materializacao.

### Security roles

- `ReqSys Solicitante`
- `ReqSys Aprovador`
- `ReqSys Administrador Low-Code`
- `ReqSys Auditor`

### Web resources

- `reqsys_/lowcode/canvas.htm`
- `reqsys_/lowcode/manifest.htm`
- `reqsys_/lowcode/dataverse-schema.htm`
- `reqsys_/lowcode/powerautomate-flows.htm`
- `reqsys_/lowcode/copilot-security-alm.htm`

### Copilot Studio

Agente nativo criado:

- Nome: `ReqSysLowCode Copilot`
- Schema: `reqsys_ReqSysLowCodeCopilot`
- Agent ID: `a5705c8f-3bcb-47b2-9b72-b2d8beaf3e53`
- Solution: `reqsys_ReqSysLowCodeCopilot`

### Custom connector e Canvas App

Custom connector nativo criado na solution `ReqSysLowCode`:

- Nome: `ReqSysLowCodeConnector`
- Connector ID: `49e39b6f-7776-f111-ab0e-7ced8da7ea1a`
- Operacoes: `ListDemandas`, `CreateDemanda`, `ListRequisitos`, `ListEvidencias`, `ListReleases`

Canvas App gerado via `pac canvas create`:

- Arquivo: `ReqSysLowCodeCanvas.msapp`
- Fonte: custom connector `49e39b6f-7776-f111-ab0e-7ced8da7ea1a`

## Checker

`ReqSysLowCode_materialized_unmanaged.zip`:

```text
Critical: 0
High: 0
Medium: 0
Low: 0
Informational: 0
```

`ReqSysLowCodeCopilot_unmanaged.zip`:

```text
Critical: 0
High: 0
Medium: 0
Low: 0
Informational: 0
```

`ReqSysLowCode_materialized_connector_unmanaged.zip`:

O checker final baixou SARIF sem resultados (`ruleId` ausente em results), apos corrigir OpenAPI metadata e icon PNG do connector.

## Pendencias tecnicas honestas

Power Automate flows foram preservados como contratos/web resources dentro da solution principal. Eles nao foram criados como flows nativos nesta rodada porque:

- Power Automate flow nativo exige definition/connection references validas para importacao segura.

Canvas App foi gerado como `.msapp` via custom connector, mas nao foi publicado automaticamente como app dentro do ambiente porque o PAC CLI gera o arquivo local e nao possui, nesta versao, comando direto para importar/publicar `.msapp` em solution.

Flows estao prontos como contrato governado dentro da solution e podem ser materializados na proxima etapa com:

- flow definitions reais com connection references por ambiente.
