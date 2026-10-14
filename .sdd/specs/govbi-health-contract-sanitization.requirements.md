# Saúde externa e sanitização do GovBI

## Contexto

O snapshot operacional consultava `/health` e classificava qualquer HTTP abaixo de 500 como verde. Isso aceitava 401/404 como saúde e divergia do contrato Spring Actuator do serviço GovBI IA. Endpoints locais também não distinguiam configuração válida, contrato local e saúde externa, e podiam refletir uma URL configurada com componentes sensíveis.

## Critérios de aceite

1. O probe externo usa somente `GET <GOVBI_BASE_URL>/actuator/health`, timeout limitado e redirects desabilitados.
2. Estado verde exige simultaneamente HTTP 200, objeto JSON e `status == "UP"`.
3. HTTP 401, 404, 5xx, timeout, JSON inválido e payload fora do contrato não podem resultar em verde.
4. `GOVBI_BASE_URL` rejeita userinfo, path, query e fragmento; nenhum erro ou resposta reflete o valor rejeitado.
5. Todo acesso HTTP GovBI exige host exato presente em `GOVBI_ALLOWED_HOSTS`; allowlist ausente ou divergente falha antes de I/O.
6. `/api/govbi/health` relata configuração e contrato local sem alegar saúde externa não verificada.
7. `/api/govbi/funcionamento` identifica seu escopo local e exibe, no máximo, origem sanitizada sem credenciais/path/query.
8. Testes automatizados cobrem sucesso, 401, 404, 5xx, timeout, resposta inválida, URL sensível e host fora da allowlist.
9. Mocks unitários não são apresentados como E2E ou prova do runtime real.

## Limites

Sem chamada a LLM, banco ou runtime GovBI real; sem POST de diagnóstico, redirects, deploy, reinício, credencial, mudança no repositório `govbi-ia` ou merge.
