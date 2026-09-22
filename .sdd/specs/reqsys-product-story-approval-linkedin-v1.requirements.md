# ReqSys Product Story Approval + LinkedIn Adapter v1

## Objetivo

Adicionar uma etapa governada de aprovação entre o Product Story Engine e a futura publicação externa, implementando o contrato oficial da LinkedIn Posts API sem habilitar publicação real neste incremento.

## Requisitos

1. Consumir o JSON `product-story-candidates.json` produzido pelo Product Story Engine.
2. Aceitar somente candidatos com `status=READY_FOR_HUMAN_REVIEW` e `selected_for_review=true`.
3. Exigir correspondência exata do `content_hash` SHA-256 selecionado.
4. Exigir confirmação explícita `APPROVE`, identidade do aprovador e `correlation_id`.
5. Distinguir aprovação `human` de aprovação `test`.
6. O modo `publish` deve rejeitar aprovação `test`.
7. Construir payload de texto conforme LinkedIn Posts API em `POST https://api.linkedin.com/rest/posts`.
8. Usar `X-Restli-Protocol-Version: 2.0.0` e `Linkedin-Version: 202609`.
9. Aceitar autores `urn:li:person:*` ou `urn:li:organization:*`.
10. Publicação real deve falhar fechada sem `REQSYS_LINKEDIN_PUBLISH_ENABLED=true` e `LINKEDIN_ACCESS_TOKEN`.
11. Em resposta 201, capturar o `x-restli-id` como identificador do post.
12. Usar o issue #1862 como ledger persistente e auditável por `content_hash`.
13. Antes da chamada externa, criar reserva `PREPARED`; uma entrada `PUBLISHED`, `PREPARED` ou `RECONCILE_REQUIRED` deve impedir retry automático.
14. Depois de HTTP 201, atualizar a mesma entrada para `PUBLISHED` com `post_id`.
15. Se o LinkedIn publicar e a atualização final do ledger falhar, marcar `RECONCILE_REQUIRED` quando possível e bloquear retry automático.
16. O workflow deste incremento deve executar somente `dry_run`, sem referenciar segredo do LinkedIn.
17. Em PR, regenerar candidatos no SHA atual a partir do último Weekly Accomplishment Log verde da `main`.
18. Executar controle negativo comprovando que confirmação diferente de `APPROVE` é rejeitada.
19. Fazer leitura independente do JSON de saída e confirmar `published=false`.

## Critérios de aceite (Acceptance Criteria)

1. Candidato selecionado + confirmação `APPROVE` + aprovação válida produz `DRY_RUN_APPROVED`.
2. Confirmação incorreta falha com código diferente de zero.
3. Candidato não selecionado é rejeitado.
4. Autor fora dos formatos permitidos é rejeitado.
5. Dry-run não executa chamada ao LinkedIn nem exige token.
6. Publish com aprovação de teste é rejeitado.
7. Publish sem feature flag habilitada é rejeitado.
8. Teste controlado do cliente com resposta HTTP 201 captura `x-restli-id`.
9. Primeira publicação governada cria reserva persistente, executa uma única chamada LinkedIn e finaliza o ledger como `PUBLISHED`.
10. Repetição do mesmo `content_hash` retorna `ALREADY_PUBLISHED` e não executa segunda chamada LinkedIn.
11. Ledger em `PREPARED` bloqueia retry automático.
12. Workflow de PR não contém `--mode publish`, `LINKEDIN_ACCESS_TOKEN` ou `REQSYS_LINKEDIN_PUBLISH_ENABLED`.
13. Workflow de PR baixa evidência semanal real, regenera candidatos, executa controle negativo, executa dry-run positivo e publica artifact.
14. Testes `tests/test_reqsys_product_story_linkedin.py` e `tests/test_reqsys_product_story_approval_workflow.py` passam.
15. Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato e `behind_by=0`.

## Fora de escopo

- Executar publicação real no LinkedIn.
- Criar ou armazenar access token.
- Solicitar permissões OAuth.
- Merge, deploy ou promoção de ambiente.
