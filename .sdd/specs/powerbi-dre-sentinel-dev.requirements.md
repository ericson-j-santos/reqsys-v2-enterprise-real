# Power BI DRE Sentinel DEV — Requisitos

## Objetivo

Comprovar o primeiro ciclo real mínimo `SemanticModel -> ExecuteQueries -> comparação`
no workspace DEV já existente, sem publicar os outros dez templates e sem promover
a paridade de negócio.

## Classificação

`gap_fix`, mutação DEV restrita e persistente, sem produção.

## Requisitos

1. Executar somente em `main`, `workflow_dispatch`, environment `development`.
2. O acionamento governado usa exclusivamente o comando
   `/reqsys run powerbi-dre-sentinel-dev`.
3. Exigir autorização literal interna `PUBLISH-DRE-SENTINEL-DEV`; não aceitar
   workspace, nome, ambiente ou comando arbitrário.
4. Reutilizar a identidade OIDC `CCP_AZURE_CLIENT_ID`; nenhum client secret.
5. Localizar exatamente um workspace `ReqSys - Observabilidade` em
   Admin/Member/Contributor pelo filtro oficial Fabric `roles`.
6. Revalidar no Power BI que o workspace existe, não é read-only e observar
   `isOnDedicatedCapacity`; não criar workspace/capacity/licença.
7. Criar no máximo um SemanticModel fixo `ReqSys DRE Sentinel DEV`.
8. A definição usa TMSL público: `definition.pbism` + `model.bim`, contendo
   apenas `_Medidas[Meta] = 0` e uma linha estática M.
9. Se o canário já existir, não atualizar: ler `getDefinition` e exigir a
   definição esperada. Definição divergente bloqueia.
10. Após uma criação, repetir a mesma decisão e comprovar que o mesmo item é
    reutilizado sem segundo POST de criação.
11. Nunca executar DELETE, hard delete, updateDefinition, refresh, push rows,
    import PBIX, criação de report ou mutação de billing/RBAC.
12. Descobrir o semantic model correspondente no Power BI e executar
    `EVALUATE ROW("value", '_Medidas'[Meta])`; exigir valor numérico zero.
13. Executar controle negativo com medida inexistente e exigir rejeição.
14. `metric_parity_promoted=false` e `representative_business_metric=false`
    em qualquer sucesso: o canário prova transporte e avaliação DAX, não
    paridade dos 143 casos.
15. Erro de licença/capacidade/permissão interrompe o fluxo; é proibido comprar,
    criar capacidade, alterar licença ou fazer fallback mutante.
16. Evidência não persiste IDs/nome remoto do workspace/model/dataset; somente
    refs SHA-256 truncadas e o nome lógico da medida podem ser gravados.
17. Registrar explicitamente:
    `new_capacity_or_license_requested=false`,
    `billing_mutation_performed=false`,
    `production_touched=false`, `stg_hml_touched=false`.
18. Testes cobrem: criação positiva, replay idempotente, item divergente,
    duplicidade, rejeição por licença/capacidade, ExecuteQueries indisponível,
    divergência do valor, controle negativo e gate main/dispatch/autorização.
19. Após a criação inicial comprovada, a rota governada opera em modo
    `reuse-only`: exige o SemanticModel existente, bloqueia antes de qualquer
    escrita se ele estiver ausente e aceita apenas workspace Power BI Pro em
    capacidade compartilhada. Nesse modo, a evidência registra
    `incremental_cost_verified_zero=true` somente quando nenhuma criação ocorreu.

## Critérios de aceite

- testes e Ruff verdes no SHA;
- SDD e workflow surface budget verdes;
- workflow existente é reutilizado; nenhum arquivo de workflow adicional;
- publicação real só ocorre após merge explícito da mudança em `main`;
- run real registra `semantic_model_definition_verified=true`;
- run real registra `idempotency_verified=true`;
- run real registra `execute_queries_status=200`;
- run real registra `sentinel_value=0`;
- controle negativo detectado;
- nenhuma operação de billing/RBAC/capacity/licença;
- o replay governado registra `reuse_only=true`,
  `workspace_shared_capacity=true`, `semantic_model_created=false` e
  `incremental_cost_verified_zero=true`;
- paridade global continua falsa.
