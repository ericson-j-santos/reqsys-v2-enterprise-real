# Continuação das integrações DEV

Requisito solicitado pelo usuário: executar as correções das integrações ReqSys no DEV e registrar as ações pendentes, considerando os erros existentes no CI.

## Critérios de aceite

- Resolver o endereço DEV pelo localizador canônico assinado; ausência de endereço válido bloqueia a execução.
- Verificar saúde e SHA do runtime; reprocessar Planner somente com SHA esperado informado e confirmado.
- Exigir o token de serviço sem registrar seu valor ou mensagens remotas potencialmente sensíveis.
- Reutilizar o reprocessador existente, sem criar outro worker recorrente.
- Rejeitar respostas inválidas da fila e retornar falha no modo estrito para erro de negócio, inclusive com HTTP 200.
- Registrar evidência de bloqueios externos e manter a validação real de Redmine pendente até sua execução.
- Não alterar homologação ou produção.

## Verificação

Os testes declarados no manifesto cobrem endereço indisponível, token ausente, SHA divergente, isolamento do localizador, invocação do reprocessador, resposta inválida e falha de negócio. A evidência local não substitui a validação dos conectores no host DEV.
