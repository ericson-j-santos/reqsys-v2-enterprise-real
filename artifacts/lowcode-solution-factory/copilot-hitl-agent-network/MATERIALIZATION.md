# Materialização da Solution ReqSys Copilot HITL

## Objetivo

Transformar o blueprint canônico da rede de agentes em um pacote Power Platform versionável e validável por PAC CLI, sem importar automaticamente em qualquer ambiente.

## Comando local

```bash
python scripts/materialize_copilot_hitl_solution.py
```

Para validar o ZIP com o Power Platform CLI instalado:

```bash
python scripts/materialize_copilot_hitl_solution.py --validate-with-pac
```

## Saídas

Diretório padrão:

```text
artifacts/lowcode-solution-factory/copilot-hitl-agent-network/generated/
├── src/
│   ├── Other/Solution.xml
│   └── customizations.xml
├── ReqSysCopilotHITL_unmanaged.zip
├── deployment-settings.json
├── connection-references.json
├── environment-variables.json
├── blueprint.snapshot.json
└── materialization-manifest.json
```

## Connection references

O pacote declara referências lógicas para:

- Dataverse;
- Microsoft Teams;
- Approvals;
- GitHub;
- Azure DevOps;
- HTTP governado para Redmine e integrações compatíveis com OpenAPI.

Os identificadores reais de conexão não são gravados no repositório. Devem ser preenchidos no `deployment-settings.json` por ambiente ou por pipeline seguro.

## Environment variables

Variáveis previstas:

- `reqsys_GitHubRepository`;
- `reqsys_AzureDevOpsOrganization`;
- `reqsys_AzureDevOpsProject`;
- `reqsys_RedmineBaseUrl`;
- `reqsys_TeamsEscalationChannelId`;
- `reqsys_ApprovalSlaHours`;
- `reqsys_MaxRetryAttempts`.

Segredos, tokens e client secrets permanecem fora da Solution e devem utilizar connection references, GitHub Environments, Azure Key Vault ou secret store equivalente.

## Pipeline

O workflow `Copilot HITL Solution Materialization` executa:

1. testes de contrato;
2. geração determinística da estrutura Power Platform;
3. criação do ZIP unmanaged;
4. validação estrutural obrigatória;
5. validação PAC CLI opcional em execução manual;
6. publicação de artifact com retenção de 30 dias.

## Governança de implantação

- DEV: importação unmanaged permitida após CI verde.
- STG: importação somente via pipeline e environment settings revisados.
- PROD: bloqueada por padrão e condicionada a aprovação Analista → PO → Gestor.
- Nenhum fluxo deste incremento realiza importação automática.
- Rollback exige export anterior e registro de evidência com `correlation_id`.

## Critérios de aceite

- ZIP contém `Other/Solution.xml` e `customizations.xml`.
- Solution é unmanaged e possui nome único `ReqSysCopilotHITL`.
- Connection references não contêm IDs ou segredos reais.
- Environment variables são separadas por ambiente.
- Artifact só é produzido após testes de contrato.
- Produção continua dependente de aprovação humana explícita.
