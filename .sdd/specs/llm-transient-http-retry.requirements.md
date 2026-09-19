# Retry HTTP transitório para providers LLM

## Requisito 1 — retry limitado
A porta comum de LLM deve repetir somente erros transitórios: HTTP 408, 429, 500, 502, 503 e 504, além de falhas de conexão/timeout já suportadas.

## Requisito 2 — fail-fast para erro permanente
HTTP 401, 403, 404 e demais respostas não transitórias não podem ser repetidas automaticamente.

## Requisito 3 — backoff e circuito
O retry deve reutilizar o backoff exponencial e o circuit breaker existentes no ADR-010, sem criar um segundo mecanismo concorrente.

## Requisito 4 — segurança
Nenhuma chave de provider, token ou payload sensível pode ser incluído em evidência. Mensagens de erro permanecem truncadas/sanitizadas pelo gateway.

## Requisito 5 — sem duplicar conversa
A retentativa ocorre dentro da chamada HTTP ao provider, antes de o endpoint retornar erro definitivo ao cliente. O cliente PC24x7 não deve repetir a criação inteira da conversa para tratar um 5xx transitório.

## Critérios de aceite
1. Dois HTTP 502 seguidos por sucesso resultam em três chamadas e sucesso final.
2. HTTP 429 persistente esgota exatamente três tentativas e permanece erro.
3. HTTP 403 executa somente uma tentativa.
4. Falhas de conexão/timeout continuam cobertas.
5. Os testes existentes de circuit breaker permanecem verdes.
