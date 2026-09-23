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
12. O E2E deve provar NORMAL→ESTUDO→ESTUDO(idempotente)→NORMAL, autenticação,
    leitura independente e bloqueio de trabalho normal durante ESTUDO.
13. A reconciliação deve exigir os bind mounts efetivos do backend e frontend.
    O bind de `infra/nginx/default.dev.conf` deve coincidir exatamente com o
    `com.docker.compose.project.working_dir` observado no próprio serviço
    `nginx`; não se pode presumir que esse diretório seja o mesmo da API.
    A atualização ocorre nos arquivos montados, sem recriar containers nem
    reprocessar `.env`.
14. Após sincronizar os binds, reiniciar somente o container API DEV já
    existente para carregar deterministicamente o código atualizado; em seguida,
    executar `nginx -t` e apenas o reload do processo Nginx existente. Não
    executar `docker compose`, não recriar a stack e não reler `.env`/segredos.
    Somente então comprovar HTTP 200 em `/api/health` e
    `/api/runtime/health` e HTTP 401 na rota protegida
    `/api/v1/noteri/profile`.
15. Quando `NOTERI_CONTROL_PLANE_URL` não estiver explicitamente configurada,
    o endpoint fixo `http://host.docker.internal:8787` pode ser inferido
    somente em container de desenvolvimento e somente quando o modo legado por
    arquivo não estiver configurado. HML/PROD e execução fora de container não
    recebem esse fallback.

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
    nem `docker compose up`. Após sincronizar os binds, pode reiniciar somente
    o container API DEV já existente via `docker restart`, preservando sua
    configuração efetiva e sem reler `.env`/segredos ou recriar a stack.
13. Bind ausente, bind do Nginx divergente do working directory declarado
    pelo próprio serviço `nginx`, fonte do bind inexistente, `nginx -t`
    inválido ou qualquer rota de saúde/controle não observada deve falhar
    fechado antes da mudança de perfil.
14. O E2E deve comprovar que o reinício controlado da API e o reload do Nginx
    restauraram `/api/runtime/health`, que a API carregou a rota same-origin e que o ciclo
    NORMAL→ESTUDO→ESTUDO(idempotente)→NORMAL terminou em NORMAL.

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
