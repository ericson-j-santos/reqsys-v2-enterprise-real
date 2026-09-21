# Fabric Identity Read-only Probe — Requisitos

## Objetivo

Validar se a identidade já configurada no environment `reqsys-power-platform-dev` pode ser reaproveitada para Microsoft Fabric, Power BI, Microsoft Graph e leitura de metadados GitHub, sem criar ou rotacionar credenciais e sem expor segredo.

## Classificação

`gap_fix`.

## Requisitos

1. O workflow deve executar somente em `pull_request` quando o próprio arquivo for alterado ou por `workflow_dispatch`.
2. O job deve usar o environment `reqsys-power-platform-dev` e permissões GitHub mínimas de `contents: read`.
3. Valores de `POWER_PLATFORM_CLIENT_SECRET`, `GITHUB_PAT` e tokens obtidos não podem ser impressos nem gravados em artefato.
4. A evidência publicada deve conter apenas status, rótulos não secretos e identificadores/nomes retornados pelas APIs acessíveis.
5. Ausência da configuração `POWER_PLATFORM_*` deve falhar de forma explícita e ainda permitir a publicação da evidência sanitizada disponível.
6. O probe deve permanecer somente leitura: nenhuma criação, rotação, exclusão, alteração de permissão, deploy ou promoção de ambiente.
7. A especificação e o teste automatizado desta funcionalidade devem acompanhar a alteração para satisfazer o gate SDD.
8. A branch do PR deve estar reconciliada com a `main` corrente antes de `READY_FOR_PR=passed`.

## Controles negativos

- O workflow não pode usar `pull_request_target`.
- O workflow não pode ampliar `permissions` para escrita.
- O contrato deve manter `secret_value_exposed=false`.
- A saída do probe não pode conter comandos que imprimam diretamente `CLIENT_SECRET`, `CROSS_REPO_PAT` ou bearer tokens.

## Critérios de aceite

- `tests/test_fabric_identity_readonly_probe_workflow.py` verde.
- `Pre-PR Readiness Gate` verde no HEAD final, com `behind_by=0` e `sdd:contract=passed`.
- `Fabric Identity Read-only Probe` verde no mesmo HEAD.
- Demais checks obrigatórios da PR sem falha determinística atribuível a esta alteração.
