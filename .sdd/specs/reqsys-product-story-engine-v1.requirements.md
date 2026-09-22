# ReqSys Product Story Engine v1

## Objetivo

Transformar o log semanal evidenciado do ReqSys em drafts governados para apresentação pública do produto, preservando rastreabilidade por PR/SHA e exigindo aprovação humana antes de qualquer publicação externa.

## Requisitos

1. Consumir somente o artifact `reqsys-weekly-accomplishment-log`.
2. Considerar publicável para revisão somente item com `implemented`, `validated`, `evidenced` e `consolidated` verdadeiros.
3. Bloquear candidatos com lacunas de evidência, PR/SHA ausentes ou sinais de conteúdo sensível.
4. Gerar `content_hash` SHA-256 determinístico a partir de PR, SHA e texto do post para suportar idempotência.
5. Produzir JSON e Markdown com fonte, evidência, blockers, score operacional, texto draft e brief visual.
6. Manter `mode=review_only`, `human_review_required=true` e `automatic_publish=false`.
7. O workflow deve ser acionado pelo sucesso do `ReqSys Weekly Accomplishment Log` e permitir execução manual para reconstrução.
8. Em Pull Requests que alterem o próprio Product Story Engine, o workflow deve executar o fluxo real usando o último artifact semanal verde da `main`, permitindo validação ponta a ponta antes do merge.
9. O workflow deve ter apenas permissões de leitura e não chamar API de publicação do LinkedIn.

## Critérios de aceite (Acceptance Criteria)

1. Um item completo e sem sinal sensível resulta em `READY_FOR_HUMAN_REVIEW`.
2. Falta de `validated`, `evidenced`, `consolidated` ou `implemented` resulta em `BLOCKED`.
3. `evidence_gaps` não vazio resulta em `BLOCKED`.
4. Título ou path contendo termo sensível configurado resulta em `BLOCKED`.
5. A mesma entrada PR/SHA/texto produz o mesmo `content_hash`.
6. Com `limit=1`, somente o candidato elegível de maior score operacional é selecionado.
7. O Markdown informa explicitamente que nenhuma publicação é automática e que revisão humana é obrigatória.
8. O contrato do workflow comprova `workflow_run` a partir do log semanal, execução de validação em PR para arquivos do próprio engine, artifact fonte exato, permissões read-only e ausência de integração de postagem externa.
9. A execução de PR baixa um `reqsys-weekly-accomplishment-log` verde da `main`, executa o gerador real e publica o artifact `reqsys-product-story-engine`.
10. Os testes `tests/test_reqsys_product_story_engine.py` e `tests/test_reqsys_product_story_workflow.py` passam.
11. O Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato e `behind_by=0` antes da abertura de PR.

## Fora de escopo

- Publicar no LinkedIn.
- Solicitar permissões `w_member_social` ou `w_organization_social`.
- Alterar secrets, produção, deploy ou promoção de ambiente.
