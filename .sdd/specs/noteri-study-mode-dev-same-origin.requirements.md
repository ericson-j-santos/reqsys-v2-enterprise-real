# Modo ESTUDO no DEV público — requisitos

## Problema evidenciado

O Task Console já usa a rota same-origin `/api/v1/noteri/profile`, porém o
runtime DEV público roda no PC24x7/Desktop e o perfil canônico pertence ao host
`Noteri`. Montar `%LOCALAPPDATA%/ReqSys/TodoGlobal24x7` no container do
Desktop altera o host errado e não pode ser usado como transporte.

O runtime público observado também respondeu 404 para
`/api/v1/noteri/profile`, comprovando que a publicação vigente está atrás do
contrato de código atual.

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
