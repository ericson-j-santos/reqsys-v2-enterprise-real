# AI Conversation API — redacao segura de erros

## Objetivo

Eliminar a exposicao do texto interno de excecoes nas respostas HTTP da Central de Conversas de IA, preservando os codigos HTTP e os controles existentes.

## Requisitos

1. `backend/app/api/ai_conversation.py::_http_error` nao pode devolver `str(exc)` em nenhum erro de dominio/provedor.
2. Os status HTTP existentes devem permanecer: 404, 403, 429, 409, 503, 502 e 500.
3. Cada classe conhecida deve retornar mensagem publica estatica adequada ao contrato, sem token, URL interna, caminho, payload ou texto da excecao.
4. O fallback generico deve continuar retornando 500 com a mensagem publica ja existente.
5. O teste de mapeamento deve cobrir todas as classes tratadas e injetar um marcador interno sensivel.
6. Um teste HTTP via `TestClient` deve provar que o marcador interno de falha do provedor nao aparece no corpo da resposta.
7. O Vibe Security Gate deve deixar de apontar os seis blockers `risk_id=12` deste arquivo sem allowlist, supressao ou relaxamento do scanner.
8. Nenhum deploy, ambiente, segredo, permissao ou guardrail de autenticacao/autorizacao faz parte deste incremento.

## Acceptance Criteria

- seis retornos `detail=str(exc)` sao removidos;
- o marcador interno dos testes nunca aparece no detalhe ou corpo HTTP;
- os codigos HTTP existentes permanecem inalterados;
- os testes da AI Conversation API passam;
- `security:changed-diff` passa sem novo blocker;
- Pre-PR Readiness fica verde no HEAD exato e com `behind_by=0`;
- nenhuma mudanca de deploy, producao, segredo ou permissao e executada.
