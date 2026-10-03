# Alinhamento do modelo Ollama no Desktop

## Requisito 1 — escopo local
A configuração deve ser aplicada somente ao perfil do usuário Windows e não deve alterar o default global do ReqSys.

## Requisito 2 — modelo único para os dois caminhos
`CODEX_OLLAMA_MODEL` e `CODEX_OLLAMA_GATEWAY_MODEL` devem receber o mesmo modelo selecionado, evitando divergência entre provider direto e `ollama_gateway`.

## Requisito 3 — endpoint local
`CODEX_OLLAMA_BASE_URL` deve aceitar apenas HTTP loopback (`localhost`, `127.0.0.1` ou `::1`). URLs remotas ou com credenciais devem ser recusadas.

## Requisito 4 — rollback
Antes da alteração, os valores anteriores das três chaves devem ser persistidos em backup local. O comando de rollback deve restaurar exatamente os valores anteriores ou remover chaves que antes não existiam.

## Requisito 5 — sem segredos
A rotina não pode ler, gravar ou imprimir tokens, chaves, senhas ou conteúdo de `.env`.

## Requisito 6 — validação
Após aplicar ou reverter, a rotina deve reler o registro e falhar se o estado observado divergir do solicitado.

## Critérios de aceite
1. `gemma4:31b-cloud` é aceito como modelo válido.
2. Metacaracteres de shell no nome do modelo são recusados.
3. Endpoint loopback é aceito e endpoint remoto é recusado.
4. Os providers direto e gateway recebem o mesmo modelo.
5. O estado persistido é validado após escrita.
6. A operação informa que processos já existentes precisam ser reiniciados para herdar o novo ambiente.
