# ReqSys Report Factory — RDL/Fabric

## Objetivo

Gerar relatórios paginados de forma declarativa e versionável, reduzindo edição manual de XML e evitando dependência do Power BI Report Builder para tarefas repetitivas.

## Gerar e validar

```bash
python tools/geradores/report_factory.py validate \
  --spec examples/report-factory/demandas_por_status.json

python tools/geradores/report_factory.py generate \
  --spec examples/report-factory/demandas_por_status.json \
  --output artifacts/report-factory/DemandasPorStatus.rdl

python tools/geradores/report_factory.py fabric-payload \
  --spec examples/report-factory/demandas_por_status.json \
  --output artifacts/report-factory/DemandasPorStatus.fabric.json

python -m pytest tests/test_report_factory_rdl.py -q
```

## Publicar em Fabric DEV

A publicação é opcional e não ocorre sem credenciais fornecidas em runtime.

```bash
export FABRIC_ACCESS_TOKEN="<token provisionado pelo ambiente>"

python tools/geradores/report_factory.py publish \
  --spec examples/report-factory/demandas_por_status.json \
  --workspace-id "<workspace-dev-id>"
```

Para atualizar item existente:

```bash
python tools/geradores/report_factory.py publish \
  --spec examples/report-factory/demandas_por_status.json \
  --workspace-id "<workspace-dev-id>" \
  --report-id "<paginated-report-id>"
```

## Segurança

- Não colocar senha, `User ID`, token ou client secret em `connect_string`.
- Não versionar `FABRIC_ACCESS_TOKEN`.
- O MVP exige `integrated_security=true` no datasource SQL.
- STG/PROD não estão autorizados por este incremento.

## Critério de evidência

O teste local comprova o contrato e a geração. Ele **não** comprova que o Fabric aceitou/renderizou o relatório.

Para evidência Fabric DEV, registrar:

- branch/SHA;
- `correlation_id` da execução;
- workspace DEV;
- request/result da criação ou atualização sem token;
- `x-ms-operation-id` quando houver LRO;
- leitura independente da definição publicada;
- posteriormente, exportação real PDF/XLSX.
