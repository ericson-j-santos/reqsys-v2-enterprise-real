# Power BI Template Runtime Resolver — Requisitos

## Objetivo

Associar, por leitura autenticada OIDC, os 11 templates de dashboards ao runtime Power BI visível
à identidade governada do ReqSys. O resolvedor deve falhar fechado para nomes ambíguos e não pode
persistir ou imprimir nomes/GUIDs remotos.

## Classificação

`gap_fix`.

## Requisitos

1. A identidade é obtida exclusivamente por Azure OIDC no environment `development`; nenhum secret estático.
2. Inventário remoto permite somente GET de workspaces, reports e datasets.
3. O único POST permitido é `executeQueries`, tratado como consulta sem mutação.
4. Não executar import, refresh, push rows, criação, atualização, exclusão ou publicação.
5. Matching usa alias exato ou assinatura determinística de domínio; fuzzy matching é proibido.
6. Binding exige exatamente um semantic model candidato. Zero = `unmatched`; mais de um = `ambiguous`.
7. Evidência persistida usa apenas `template_id` e referências SHA-256 truncadas; nomes e IDs brutos ficam somente em memória.
8. Logs não podem imprimir nomes/GUIDs remotos, tenant/client ID ou token.
9. O primeiro ciclo de paridade é um sentinel DRE `_Medidas[Meta]`, cuja definição local extraída é constante `0`. A consulta usa exclusivamente o dataset sintético identificado pelo nome e nunca o modelo empresarial DRE.
10. Sentinel serve para provar transporte/execução e nunca promove `metric_parity_verified`.
11. HTTP 401/403/404/429, resposta inválida ou binding ausente/ambíguo produzem bloqueio explícito.
12. O job OIDC em pull request só executa para PR do próprio repositório criado pelo proprietário.
13. O artifact registra `mutations_performed=false`, `secret_value_exposed=false`,
    `raw_remote_ids_persisted=false`, `raw_remote_names_persisted=false` e
    `raw_remote_ids_or_names_logged=false`.
14. O resolvedor deve reutilizar o workflow canônico `fabric-oidc-readonly-probe.yml`; é proibido aumentar a superfície de workflows só para esse caso.
15. O preflight também deve observar `isReadOnly`, `isOnDedicatedCapacity` e o papel da App
    no workspace via `GET /groups/{groupId}/users`, sem persistir o identificador da App.
16. Para resolver divergência do endpoint clássico, consultar também somente por GET
    `/v1/workspaces/{workspaceId}/roleAssignments` no Fabric e casar apenas
    `servicePrincipalDetails.aadAppId` exatamente com `CCP_AZURE_CLIENT_ID`.
17. O resultado pode marcar `write_candidate=true` apenas para Admin/Member/Contributor
    observado no Power BI ou no Fabric em workspace não read-only.
18. HTTP 403/401 do Fabric roleAssignments permanece estado desconhecido/bloqueado e não pode
    ser convertido em permissão por inferência.
19. A API não pode inferir custo: `incremental_cost_verified_zero` permanece false até existir
    evidência independente de cobrança/licenciamento; o probe não pode criar capacidade/licença.
20. Testes cobrem caso positivo, ambiguidade, 403 em ExecuteQueries, divergência do sentinel,
    bloqueio de endpoint mutante, assinatura de domínio, divergência Power BI/Fabric,
    role/capacidade e contrato do workflow.
21. O modelo sintético `ReqSys DRE Sentinel DEV` nunca pode ser candidato de
    template empresarial, mesmo quando o relatório associado possui alias DRE.
    Relatórios sem dataset visível também não produzem bindings por inferência.
22. O ExecuteQueries de `_Medidas[Meta]` deve usar exclusivamente o ID do
    sentinela sintético identificado no inventário; sentinela ausente/ambíguo
    bloqueia essa consulta e nunca é substituído pelo dataset empresarial.

## Critérios de aceite

- contrato local verde no SHA exato;
- Ruff/gates SDD e readiness verdes para os arquivos alterados;
- workflow canônico sem crescimento líquido de arquivos em `.github/workflows`;
- execução OIDC real em `development` com artifact sanitizado;
- inventário de workspaces/reports/datasets e role/capacidade do workspace concluído sem mutação;
- ausência de nomes/GUIDs remotos em logs e artifact;
- binding `resolved`, `unmatched` ou `ambiguous` registrado por template sem fuzzy;
- sentinela DRE excluído por nome de modelo e vínculo datasetId, com testes positivo/negativo;
- sentinel executado somente se o próprio dataset sintético possuir binding único, independente do DRE empresarial;
- `metric_parity_promoted=false` em qualquer resultado do sentinel.
