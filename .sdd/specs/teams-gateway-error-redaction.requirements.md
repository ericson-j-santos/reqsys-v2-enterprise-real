# Redacao segura de erros do Teams Gateway

## Objetivo

Eliminar a exposicao de mensagens internas de excecao nas respostas HTTP do Teams Gateway sem alterar autenticacao, autorizacao, status HTTP ou integracoes externas.

## Requisitos

1. Nenhum handler de `backend/app/api/teams_gateway.py` pode devolver `str(exc)` diretamente ao cliente.
2. Erros de dominio esperados devem preservar o status HTTP atual e retornar mensagem publica estatica por operacao.
3. O detalhe original da excecao nao pode aparecer no corpo HTTP, mesmo quando contiver token, segredo ou dado interno.
4. Erros HTTP upstream ja sanitizados por status code permanecem inalterados.
5. A mudanca nao pode alterar autenticacao, autorizacao, deploy, ambientes ou segredos.
6. O Vibe Security Gate deve deixar de apontar os sete blockers `risk_id=12` deste arquivo.
7. Testes HTTP devem cobrir CRUD de destinatarios, CRUD de owners, consulta de Solution, clonagem e promocao.

## Criterios de aceite

- testes de regressao HTTP aprovados;
- `tests/test_vibe_security_gate.py` aprovado;
- `vibe_security_gate.py --strict --scope changed` aprovado para o diff;
- Pre-PR Readiness verde no HEAD exato e `behind_by=0`;
- nenhum valor interno injetado no teste aparece na resposta.
