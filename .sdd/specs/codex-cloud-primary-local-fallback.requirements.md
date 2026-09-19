# Codex — cloud primário com fallback local

## Requisito 1 — primário
No Desktop, `gemma4:31b-cloud` deve permanecer como modelo primário dos providers Ollama direto e gateway.

## Requisito 2 — fallback
`gemma4:26b-q8-code` deve ser configurável como fallback local e usado somente quando a tentativa do modelo primário falhar por erro HTTP/rede do provider.

## Requisito 3 — evidência
O gateway deve devolver:
- `requested_model`: modelo solicitado;
- `model`: modelo efetivamente usado;
- `fallback_used`: se houve fallback.

## Requisito 4 — propagação
O backend ReqSys deve propagar `CODEX_OLLAMA_FALLBACK_MODEL` tanto para o provider direto quanto para o `ollama_gateway`.

## Requisito 5 — segurança e escopo
A configuração persistente deve permanecer no perfil local do Windows, sem editar `.env`, sem segredos e sem deploy/promoção de ambiente.

## Critérios de aceite
1. Primário cloud funciona no E2E real.
2. Controle negativo de cloud indisponível aciona o 26B local.
3. Modelo efetivo e uso de fallback são observáveis.
4. Testes unitários cobrem fallback direto, payload do gateway, resposta do gateway e persistência Windows.
5. Nenhuma chamada E2E publica payload no ReqSys nem toca produção.
