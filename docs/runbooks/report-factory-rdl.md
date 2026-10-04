# ReqSys Report Factory — RDL/Fabric

## Objetivo

Gerar relatórios paginados de forma declarativa e versionável, reduzindo edição manual de XML e evitando dependência do Power BI Report Builder para tarefas repetitivas.

## Núcleo compartilhado

O gerador/validador genérico é consumido do repositório `ericson-j-santos/report-builder-platform`
por uma dependência Git fixada em SHA imutável. O arquivo
`tools/geradores/report_factory.py` é apenas um adaptador de compatibilidade que preserva o
namespace determinístico histórico `reqsys:report-factory`.

Antes de executar localmente:

```bash
python -m pip install -r requirements-report-builder.txt
```

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

## Publicação E2E governada em DEV

O preflight manual continua somente leitura por padrão. A mutação DEV usa o mesmo workflow, sem criar uma nova superfície de Actions, e só é habilitada pelo modo explícito `publish-e2e`.

No canal governado do ReqSys (issue operacional #1705), o comando exato é:

```text
/reqsys run report-factory-fabric-dev-e2e
```

O gateway fixa `main`, o workflow fixa o environment `development` e o script fixa o workspace `ReqSys - Observabilidade`. Não há input de workspace, ambiente produtivo, token ou workflow arbitrário.

A evidência só é aceita quando o mesmo run comprova:

- exatamente um workspace DEV alvo;
- exatamente um relatório com o nome da `ReportSpec`;
- criação ou atualização concluída;
- `getDefinition` independente;
- SHA-256 do RDL lido igual ao RDL gerado;
- replay da mesma definição sem duplicidade;
- `secret_value_exposed=false`;
- `production_touched=false`.
