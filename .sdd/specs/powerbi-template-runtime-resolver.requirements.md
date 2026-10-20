# Power BI template runtime resolver — requirements

## Objetivo

Associar, por leitura autenticada OIDC, os 11 templates de dashboards ao runtime Power BI visível
à identidade governada do ReqSys. O resolver deve falhar fechado para nomes ambíguos e não pode
persistir ou imprimir nomes/GUIDs remotos.

## Requisitos

1. A identidade é obtida exclusivamente por Azure OIDC no environment `development`; nenhum secret estático.
2. Inventário remoto permite somente GET de workspaces, reports e datasets.
3. O único POST permitido é `executeQueries`, que é tratado como consulta sem mutação.
4. Não executar import, refresh, push rows, criação, atualização, exclusão ou publicação.
5. Matching é exato após normalização; fuzzy matching é proibido.
6. Binding exige exatamente um semantic model candidato. Zero = `unmatched`; mais de um = `ambiguous`.
7. Evidência persistida usa apenas `template_id` e referências SHA-256 truncadas; nomes e IDs brutos ficam somente em memória.
8. Logs não podem imprimir nomes/GUIDs remotos, tenant/client ID ou token.
9. O primeiro ciclo de paridade é um sentinel DRE `_Medidas[Meta]`, cuja definição local extraída é constante `0`.
10. Sentinel serve para provar transporte/execução e nunca promove `metric_parity_verified`.
11. HTTP 401/403/404/429, resposta inválida ou binding ausente/ambíguo devem produzir bloqueio explícito.
12. O workflow de PR só executa OIDC para PR do próprio repositório criado pelo proprietário.
13. O artifact deve registrar `mutations_performed=false`, `secret_value_exposed=false`,
    `raw_remote_ids_persisted=false`, `raw_remote_names_persisted=false` e
    `raw_remote_ids_or_names_logged=false`.
14. Testes devem provar caso positivo, ambiguidade, 403 em ExecuteQueries, divergência do sentinel,
    bloqueio de endpoint mutante e contrato do workflow.
