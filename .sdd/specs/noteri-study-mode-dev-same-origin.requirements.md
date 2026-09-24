# Modo ESTUDO no DEV público — requisitos

## Problema evidenciado

O Task Console já usa a rota same-origin `/api/v1/noteri/profile`, porém o
runtime DEV público roda no PC24x7/Desktop e o perfil canônico pertence ao host
`Noteri`. Montar `%LOCALAPPDATA%/ReqSys/TodoGlobal24x7` no container do
Desktop altera o host errado e não pode ser usado como transporte.

O runtime público observado também respondeu 404 para
`/api/v1/noteri/profile`, comprovando que a publicação vigente está atrás do
contrato de código atual. Em 22/09/2026, o gate externo confirmou outro drift:
`/api/health` respondeu 200, mas `/api/runtime/health` respondeu 404. Como o
backend atual expõe essa rota e o Nginx DEV atual preserva `/api/runtime/*`,
esse padrão caracteriza configuração Nginx efetiva desatualizada no PC24x7.

## Estado alvo

1. O navegador usa somente `/api/v1/noteri/profile`.
2. GET exige usuário autenticado e POST exige papel admin.
3. A API DEV do PC24x7 consulta o ReqSys Engineering Orchestrator pelo endpoint
   interno fixo `http://host.docker.internal:8787`.
4. O backend não aceita URL arbitrária de control plane: somente
   `host.docker.internal`, `127.0.0.1` ou `localhost`, porta 8787 e HTTP.
5. O estado do Noteri vem do worker fresco, autenticado e online do registry.
6. A mutação usa exclusivamente o task type `host.profile.set.v1`, destino
   `Noteri`, perfil NORMAL/ESTUDO e papel builder.
7. O worker Noteri altera somente o arquivo canônico local
   `%LOCALAPPDATA%/ReqSys/TodoGlobal24x7/host-profile.json`.
8. Escrita local deve ser atômica, com leitura independente e heartbeat
   imediato para atualizar o control plane antes de concluir a tarefa.
9. O task type de perfil pode ser despachado quando o Noteri já está em ESTUDO;
   tarefas normais continuam inelegíveis nesse estado.
10. Repetir o mesmo perfil retorna `changed=false` sem novo enqueue.
11. Nenhum comando arbitrário, GUI, Remote Desktop Commander, HML, PROD ou
    segredo faz parte deste fluxo.
12. O E2E deve ser independente do perfil encontrado no início. Antes do teste
    positivo, deve solicitar NORMAL, aceitar `changed=true` ou `changed=false`
    nessa normalização, exigir leitura independente confirmando NORMAL e
    `accepts_new_development=true` e somente então provar
    NORMAL→ESTUDO→ESTUDO(idempotente)→NORMAL. A primeira transição para ESTUDO
    após a pré-condição deve retornar `changed=true`, evitando falso positivo e
    falso negativo quando o runtime chega ao E2E já em ESTUDO.
13. A reconciliação deve exigir os bind mounts efetivos do backend e frontend.
    O bind de `infra/nginx/default.dev.conf` deve coincidir exatamente com o
    `com.docker.compose.project.working_dir` observado no próprio serviço
    `nginx`; não se pode presumir que esse diretório seja o mesmo da API.
    Na rota normal, a atualização ocorre nos arquivos montados sem recriar
    containers nem reprocessar `.env`. A única exceção é drift comprovado da
    publicação do Nginx DEV: se o serviço validado não publicar 8083, o
    reconciliador pode gerar uma definição Compose mínima contendo somente o
    Nginx observado, sua imagem allowlisted, bind validado, política de restart
    e rede externa já existente; deve recriar somente esse serviço com 8083,
    sem `environment`, build, dependências ou leitura de `.env`/segredos, e
    restaurar a publicação anterior se a validação imediata do reparo falhar.
14. Após sincronizar os binds, reiniciar somente o container API DEV já
    existente para carregar deterministicamente o código atualizado. Antes de
    tocar o Nginx, o OpenAPI direto em `127.0.0.1:8210/openapi.json` deve
    comprovar simultaneamente `/v1/noteri/profile` e `/api/runtime/health`.
    O reconciliador deve registrar de forma sanitizada qual contrato direto
    ficou ausente. O serviço Nginx selecionado deve publicar exatamente a porta
    host 8083. Se houver drift nessa publicação, o reparo restrito descrito no
    item 13 deve ocorrer antes da sincronização e o runtime deve ser descoberto
    novamente. Fora dessa exceção, não executar `docker compose` nem recriar
    containers. Após copiar a configuração, o reconciliador deve esperar até o
    bind observado dentro do container ser byte-equivalente ao arquivo host
    normalizado; somente então executar `nginx -t` e `nginx -s reload`, sem
    reiniciar novamente o Nginx e sem reler `.env`/segredos.
    Somente então comprovar HTTP 200 em `/api/health` e
    `/api/runtime/health` e HTTP 401 na rota protegida
    `/api/v1/noteri/profile`.
15. Quando `NOTERI_CONTROL_PLANE_URL` não estiver explicitamente configurada,
    o endpoint fixo `http://host.docker.internal:8787` pode ser inferido
    somente em container de desenvolvimento e somente quando o modo legado por
    arquivo não estiver configurado. HML/PROD e execução fora de container não
    recebem esse fallback.
16. Quando a validação do gateway DEV não observar o status esperado, a
    evidência de falha deve capturar, antes do rollback e sem texto bruto:
    alcance TCP de `127.0.0.1:8083`, status HTTP de `/api/health`, status do
    upstream `nginx -> api:8000/health` e presença das rotas críticas na
    configuração ativa do Nginx. O diagnóstico deve preservar também o path
    allowlisted que expirou e o último status HTTP inteiro/nulo observado por
    essa espera. A falha original permanece canônica e o diagnóstico adicional
    não pode mascará-la.

17. Alterações no contrato de runtime que podem invalidar o fluxo — API de perfil,
    API de monitoramento/runtime health, registro de routers, Compose DEV e
    configuração Nginx DEV — devem disparar novamente o E2E físico do Modo
    ESTUDO após integração na main. A ausência desse gatilho é tratada como
    risco de falso positivo e deve falhar por teste de contrato do workflow.

17. Falhas HTTP posteriores à validação do gateway devem registrar somente o
    estágio lógico da operação e o status HTTP observado (por exemplo,
    `api_admin_login` + `http_status_403`), sem persistir corpo de resposta,
    token, cabeçalho Authorization, e-mail ou dado arbitrário. O E2E deve
    verificar explicitamente se o login demo está habilitado antes de usá-lo e
    diferenciar autenticação, leitura de perfil, mudança para ESTUDO, replay e
    restauração NORMAL.

18. Quando a leitura autenticada inicial de perfil falhar com HTTP 503, o
    reconciliador deve anexar diagnóstico direto e sanitizado do registro do
    Engineering Orchestrator em 127.0.0.1:8787: alcançabilidade, status HTTP,
    validade estrutural, quantidade de workers Noteri e, somente quando houver
    exatamente um, os campos booleanos `fresh`, `controller_online`,
    `auth_valid`, `eligible` e o perfil NORMAL/ESTUDO. IDs, corpo bruto,
    capabilities, tokens, caminhos ou campos arbitrários não podem ser
    persistidos.

## Critérios de aceite

1. O frontend não acessa loopback do dispositivo do navegador.
2. GET sem autenticação retorna 401 e POST sem admin retorna 403.
3. Um worker Noteri ausente, duplicado, stale, offline ou sem auth retorna 503.
4. O POST nunca aceita task type, host ou comando fornecido pelo usuário.
5. NORMAL→ESTUDO conclui somente após resultado `host.profile.set.v1` válido,
   leitura local independente e heartbeat de readback no control plane.
6. O GET imediatamente posterior observa o novo perfil sem janela de heartbeat.
7. ESTUDO→ESTUDO é idempotente e não cria nova tarefa.
8. ESTUDO→NORMAL funciona mesmo quando desenvolvimento normal está bloqueado.
9. Erros HTTP não expõem caminhos, exceções internas ou dados sensíveis.
10. HML/PROD, deploy e merge permanecem fora deste incremento sem autorização.
11. Drift de proxy que faça `/api/runtime/health` retornar 404 deve falhar
    fechado; a reconciliação só conclui após restaurar o contrato público e
    confirmar as duas rotas de saúde por leitura HTTP independente.
12. O caminho normal do reconciliador não executa `docker compose config`
    nem `docker compose up`. A exceção controlada é reparar drift da porta
    8083 recriando somente o Nginx DEV com uma definição gerada, sem `.env`,
    segredos ou outros serviços e com rollback da publicação anterior se a
    validação do reparo falhar. Após sincronizar os binds, pode reiniciar
    somente a API DEV já existente via `docker restart`; o Nginx já correto
    recebe apenas `nginx -t` e `nginx -s reload`.
13. Bind ausente, módulo de monitoramento operacional ausente no backend
    montado, bind do Nginx divergente do working directory declarado pelo
    próprio serviço `nginx`, falha em reparar/validar a porta host 8083, fonte
    inexistente, bind ainda não visível dentro do container, contrato OpenAPI
    direto sem `/v1/noteri/profile` ou `/api/runtime/health`, `nginx -t`
    inválido ou qualquer rota de saúde/controle não observada deve falhar
    fechado antes da mudança de perfil.
14. O E2E deve comprovar primeiro no backend direto da porta 8210 que os dois
    paths críticos estão registrados; depois comprovar que o restart controlado
    da API e o reload do Nginx, sem queda do listener 8083, restauraram
    `/api/runtime/health`, que a API carregou a rota same-origin e que,
    independentemente do perfil inicial, uma pré-condição NORMAL foi aplicada e
    lida de forma independente antes de o ciclo
    NORMAL→ESTUDO→ESTUDO(idempotente)→NORMAL terminar em NORMAL.
15. Uma falha `gateway_status_timeout` deve publicar diagnóstico sanitizado
    suficiente para distinguir porta 8083 indisponível, resposta HTTP não
    esperada, falha do upstream Nginx→API e contrato Nginx ausente. Nenhuma
    saída bruta de comando, corpo HTTP, caminho local, variável de ambiente ou
    segredo pode entrar no artefato; checkpoints de estágio devem registrar
    transições materiais sem reiniciar o relógio por mero polling.

16. O workflow de reconciliação deve ser acionado por mudanças em
    `backend/app/api/noteri_host_profile.py`,
    `backend/app/api/monitoramento_operacional.py`, `backend/app/main.py`,
    `docker-compose.dev.yml` e `infra/nginx/default.dev.conf`, além dos
    componentes específicos do Modo Estudo, garantindo nova evidência física
    quando o contrato público ou a porta 8083 puderem mudar.


17. Antes de iniciar o E2E de perfil, o workflow DEV deve validar o Engineering
    Orchestrator em `127.0.0.1:8787`. Se readiness estiver indisponível, deve
    primeiro solicitar a execução da tarefa agendada existente e fixa
    `\\Automation\\ReqSysOrchestrator24x7`, sem criar/alterar tarefa, sem shell
    arbitrário e sem ler segredos. Se a tarefa retornar sucesso de acionamento
    mas `/readyz` continuar indisponível, o recovery pode iniciar diretamente
    somente o supervisor versionado da instalação canônica fixa
    `C:\\dev\\chatgpt-workers\\reqsys-orchestrator-24x7-runtime`, após validar
    `service-config.json`, `worker-config.json`, porta 8787, endpoint loopback,
    worker desktop-pdqk954 e arquivos esperados. O processo deve ser destacado
    do lifecycle do runner removendo apenas `RUNNER_TRACKING_ID`. A execução
    prossegue somente após `/readyz` saudável e exatamente um worker Noteri
    `fresh`, `controller_online` e `auth_valid`; caso contrário falha fechado
    antes da mudança de perfil. Se a instalação canônica existir mas seus
    arquivos `service-config.json` ou `worker-config.json` divergirem do
    contrato, o recovery pode normalizar exclusivamente esses dois arquivos
    para o contrato canônico (modo `control-plane-worker`, porta 8787,
    endpoint loopback, worker `desktop-pdqk954` e parâmetros operacionais
    versionados), preservando a primeira versão local em backup idempotente
    antes da escrita e revalidando o contrato após a alteração. O código do
    runtime, banco e demais arquivos não podem ser substituídos por essa rota.
    A evidência deve indicar o método de recovery e se houve normalização, sem
    persistir caminhos arbitrários, mantendo `production_touched=false`,
    `secrets_read=false` e `task_created_or_modified=false`.

## Topologia

```text
Browser
  -> ReqSys DEV público /api/v1/noteri/profile
  -> API no PC24x7/Desktop
  -> Engineering Orchestrator :8787 (host)
  -> work item host.profile.set.v1
  -> worker Noteri
  -> host-profile.json canônico
  -> heartbeat imediato
  -> leitura same-origin
```


## Correção preventiva de descoberta do runtime — 22/09/2026

O reconciliador não pode depender de nomes históricos de projeto/container Docker. O runtime DEV deve ser descoberto pela única API em execução que publica a porta host 8210, conforme o contrato de `docker-compose.dev.yml` e a evidência operacional do piloto; o projeto e os serviços `api`, `frontend` e `nginx` são validados pelos labels oficiais do Docker Compose. Projetos com identidade HML/STG/PROD são rejeitados antes de qualquer alteração.

Critério adicional: ausência ou ambiguidade da API DEV 8210, serviço Compose duplicado/ausente ou identidade não-DEV deve falhar fechado sem tocar HML/PROD. A porta 8083 permanece o gateway funcional validado por HTTP, mas não é usada como identidade Docker.
