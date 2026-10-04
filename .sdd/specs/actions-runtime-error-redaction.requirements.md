# Actions Runtime Center — redacao segura de erros

## Objetivo

Eliminar a exposicao de mensagens internas de excecao nas respostas HTTP do Actions Runtime Center, mantendo os contratos de status, autenticacao e autorizacao.

## Requisitos

1. Nenhum handler de `backend/app/api/actions_runtime_center.py` pode devolver `str(exc)` ou interpolar `exc` no campo `detail`.
2. Falhas conhecidas devem preservar o status HTTP existente e retornar uma mensagem publica estatica por operacao.
3. Falhas inesperadas de integracoes externas devem retornar erro generico sem expor token, URL interna, caminho, payload ou texto da excecao.
4. O endpoint de execucao continua exigindo `confirmar=true`; esta mudanca nao relaxa autorizacao nem guardrails de deploy DEV.
5. O erro `KeyError` de acao inexistente permanece com a mensagem publica ja segura.
6. Os testes HTTP devem injetar um marcador interno sensivel em cada classe de excecao tratada e provar sua ausencia na resposta.
7. O Vibe Security Gate deve deixar de apontar os sete blockers `risk_id=12` deste arquivo sem allowlist ou supressao.
8. Nenhum deploy, ambiente, segredo ou permissao faz parte deste incremento.

## Acceptance Criteria

- os nove caminhos de erro HTTP cobertos retornam mensagens publicas estaticas;
- o marcador interno dos testes nunca aparece no corpo da resposta;
- os status HTTP existentes permanecem 422, 502 e 404 onde aplicavel;
- testes existentes do Operational Orchestrator continuam aprovados com o novo contrato publico;
- `security:changed-diff` passa sem novo blocker;
- Pre-PR Readiness fica verde no HEAD exato e com `behind_by=0`;
- nenhuma mudanca de deploy, producao, segredo ou permissao e executada.
