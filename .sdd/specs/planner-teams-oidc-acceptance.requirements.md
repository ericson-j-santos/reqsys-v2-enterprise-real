# Planner → Teams DEV — Acceptance via GitHub OIDC

## Requisito 1 — autenticação não interativa
O acceptance DEV deve usar GitHub OIDC / Workload Identity Federation e não pode depender de Device Code, refresh token, sessão MSAL delegada ou client secret para Microsoft Graph.

## Requisito 2 — reutilização do E2E canônico
O workflow `planner-teams-notify-dev-acceptance.yml` deve reutilizar `runtime-e2e-continuous.yml` por `workflow_call`, evitando duas implementações divergentes do mesmo teste.

## Requisito 3 — prova real
O E2E deve criar duas tarefas reais no Planner:
- tarefa `REQSYS-E2E-*`: controle negativo, não deve produzir mensagem no Teams;
- tarefa normal: controle positivo, deve produzir mensagem no Teams.

A validação do efeito deve ocorrer por leitura independente do canal Teams via Microsoft Graph.

## Requisito 4 — cleanup
As tarefas criadas pelo E2E devem ser removidas ao final. Falha de cleanup mantém o run vermelho.

## Requisito 5 — segurança
Tokens OIDC são efêmeros e mascarados. Nenhum token, Device Code, refresh token ou segredo Microsoft é publicado em artifact, Summary ou log.

## Requisito 6 — compatibilidade
O nome histórico `Planner Teams Notify DEV Acceptance` permanece disponível por `workflow_dispatch`, mas delega integralmente ao Runtime E2E OIDC.

## Critérios de aceite
1. O acceptance não contém `msal_device_code`, `device_code`, `WSJF_MSAL_STORAGE_STATE_B64` ou `POWER_PLATFORM_CLIENT_SECRET`.
2. O Runtime E2E expõe `workflow_call`.
3. Os testes de contrato OIDC passam.
4. O E2E real Planner→Teams retorna `status=passed`, `auth_mode=oidc`, CT-01 negativo, CT-02 positivo e cleanup concluído.
5. Os módulos Device Code são removidos somente após busca confirmar ausência de consumidores ativos.

## Requisito 7 — flows ativos e cartão reconciliado
Antes de criar tarefas de prova, o E2E deve localizar os dois flows Planner→Teams no Dataverse, validar as referências `shared_planner` e `shared_teams` e reconciliar, quando houver drift, somente `Notificar_Teams.inputs.parameters["body/messageBody"]`.

A reconciliação deve falhar fechada se o alvo não for exatamente `shared_teams/PostCardToConversation`, usar o `@odata.etag` corrente para concorrência otimista, preservar destinatário, conexões e todo o restante do `clientdata`, reler o flow após o PATCH e validar independentemente o contrato do cartão. Se a leitura pós-PATCH divergir, deve tentar restaurar o `clientdata` original antes de falhar.

A atualização do cartão deve usar diretamente `PATCH workflows(<workflowid>)` no registro corrente com o `@odata.etag` observado, sem desativar um flow ativo apenas para editar `clientdata`. Desativar para esse fim materializa uma revisão não publicada e pode transformar o PATCH seguinte em conflito `HTTP 400 0x80040203` ("published update ... unpublished active row"). Se já existir revisão não publicada concorrente, a reconciliação deve falhar fechada, preservar o estado do flow e não tentar publicar, sobrescrever ou descartar esse draft automaticamente. Nesse conflito exato, é permitido apenas consultar a revisão com `RetrieveUnpublished()` e registrar diagnóstico sanitizado por fingerprints semânticos. O diagnóstico deve separar o hash do cartão do hash do restante do `clientdata`, permitindo classificar a revisão como `same_as_published`, `same_as_desired`, `same_non_card_desired_card`, `same_non_card_published_card`, `card_only_divergent`, `non_card_divergent` ou `unpublished_invalid`. O `clientdata` bruto, destinatários e valores de parâmetros não podem ser publicados em log ou artifact. Quando houver `non_card_divergent`, o diagnóstico pode expor apenas os caminhos estruturais JSON Pointer alterados, tipos e SHA-256 dos valores de cada lado, com limite explícito e sinalização de truncamento; os valores continuam proibidos. Os erros do Dataverse devem propagar código e mensagem para diagnóstico.

O cartão corrente deve:
- usar o título operacional do evento;
- destacar o título da tarefa;
- expor somente `Progresso` e `Vencimento` na área principal;
- não exibir o ID bruto do plano;
- usar `Sem prazo` quando aplicável;
- manter o ID da tarefa apenas como metadado secundário;
- fornecer `Abrir no Planner` para a tarefa correta.

Depois da reconciliação, o E2E deve ativar somente um flow que já estivesse inativo; a reconciliação do cartão não pode desativar um flow ativo. Após eventual ativação, deve confirmar `statecode=1/statuscode=2` e comprovar que a ativação não alterou o `clientdata` reconciliado.

## Requisito 8 — aquecimento do gatilho
Após confirmar os flows ativos, o workflow deve aguardar 15 segundos antes de criar as tarefas de prova, preservando a janela já usada pelo acceptance legado para evitar perda do primeiro evento do gatilho recém-ativado.


## Requisito 9 — prova visual do cartão
O controle positivo do Runtime E2E deve ler a mensagem real no Teams via Microsoft Graph e validar o Adaptive Card serializado no attachment. O run só pode passar quando o cartão observado contiver `Progresso` e `Vencimento`, não contiver `Plano` ou `Percentual` legados, expuser `Abrir no Planner` e o link apontar para o ID exato da tarefa criada no próprio run.
