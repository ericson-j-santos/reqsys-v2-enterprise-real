# Design — ReqSys Report Factory RDL/Fabric MVP

## Fluxo

```text
ReportSpec JSON/YAML
        |
        v
validate_spec (fail-closed)
        |
        v
generate_rdl (determinístico)
        |
        +--> validate_rdl
        |
        v
build_fabric_definition
        |
        +--> arquivo/payload para CI
        |
        v
publish_to_fabric (opcional, DEV autorizado)
        |
        v
LRO bounded polling
```

## Decisões

- **Schema-driven:** a entrada declarativa é a fonte de intenção; XML RDL é derivado.
- **Sem segredo no código:** o único token aceito pelo cliente Fabric vem de `FABRIC_ACCESS_TOKEN`.
- **Determinismo:** geração não usa horário, UUID ou estado externo.
- **Fail-closed:** referências inválidas e recursos não implementados são rejeitados.
- **Dependências mínimas:** geração JSON/RDL e cliente HTTP usam biblioteca padrão; YAML é opcional via `PyYAML`.
- **Consolidação:** reutiliza o padrão RDL já existente no ReqSys e fica em `tools/geradores`.

## API Fabric

O cliente usa:

- criação: `POST /v1/workspaces/{workspaceId}/paginatedReports`;
- atualização: `POST /v1/workspaces/{workspaceId}/paginatedReports/{reportId}/updateDefinition`;
- definição: formato `PaginatedReportDefinition`, RDL Base64, `InlineBase64`.

Operações `202` são acompanhadas por `Location` com timeout e `Retry-After`.

## E2E

O maior E2E executável sem credenciais externas é:

`ReportSpec -> RDL -> validação XML/contrato -> payload Fabric -> decode independente -> equivalência byte a byte`.

E2E real de Fabric DEV permanece obrigatório antes de declarar integração externa validada.
