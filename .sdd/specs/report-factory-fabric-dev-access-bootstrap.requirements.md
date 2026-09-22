# Report Factory — Bootstrap governado de acesso Fabric DEV

## Contexto

O preflight do Report Factory comprovou autenticação OIDC e token Fabric válidos,
mas a identidade governada do Environment `development` não enxerga nenhum
workspace. O workspace DEV alvo já existente é `ReqSys - Observabilidade`.

Issue: #1933  
Increment type: `gap_fix`

## Requisitos

1. Reutilizar a identidade OIDC governada `CCP_AZURE_CLIENT_ID`; não criar nova App Registration.
2. Executar a mutação somente por `workflow_dispatch` na `main`, no runner allowlisted Noteri.
3. O workflow deve ser inputless e disparável pelo Authorized Actions Gateway somente pelo comando exato `/reqsys run report-factory-fabric-dev-access-bootstrap`.
4. Usar a sessão Azure delegada já autenticada no Noteri e validar o tenant esperado antes da chamada Fabric.
5. Localizar exatamente um workspace com display name `ReqSys - Observabilidade`.
6. Localizar a service principal correspondente a `CCP_AZURE_CLIENT_ID` sem imprimir ou persistir seus identificadores.
7. Ler `roleAssignments` antes de qualquer escrita.
8. Se já houver Contributor, Member ou Admin, executar `noop`.
9. Se houver uma única atribuição inferior, alterar somente essa atribuição para `Contributor`.
10. Se não houver atribuição, criar exatamente uma `ServicePrincipal/Contributor`.
11. Nunca conceder Admin ou Member; Contributor é o teto da mutação.
12. Reconsultar `roleAssignments` e exigir Contributor-or-higher como pós-condição.
13. Não criar/rotacionar segredo, não tocar STG/PROD e não aceitar workspace/principal/role arbitrários.
14. Publicar artifact sanitizado com estados, papéis antes/depois e status HTTP, sem token, IDs ou segredo.
15. Falhar fechado diante de host, tenant, workspace, service principal ou atribuição ambíguos.

## Critérios de aceite

- testes de contrato verdes;
- policy self-hosted inclui somente o workflow explícito;
- Pre-PR Readiness verde no HEAD exato;
- workflow mergeado apenas pelos gates normais;
- execução governada em `main` demonstra `contributor_or_higher_after=true`;
- probe OIDC independente posterior demonstra ao menos um workspace visível;
- somente depois disso o Report Factory pode executar publicação RDL DEV.
