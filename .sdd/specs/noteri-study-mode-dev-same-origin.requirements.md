# Modo ESTUDO no DEV público — requisitos

## Problema evidenciado

O frontend do Task Console chamava diretamente `http://127.0.0.1:8765`.
Esse desenho só é válido quando o navegador está no próprio Noteri e a página
também é local HTTP. Em DEV HTTPS ele fica sujeito a mixed content/PNA/CORS; em
outro dispositivo, `127.0.0.1` aponta para o dispositivo do navegador.

## Estado alvo

1. O navegador deve usar somente a origem do próprio ReqSys:
   `/api/v1/noteri/profile`.
2. O agente local `:8765` permanece loopback-only e não é publicado.
3. A API DEV monta o diretório canônico
   `%LOCALAPPDATA%/ReqSys/TodoGlobal24x7` em `/noteri-runtime`.
4. GET exige usuário autenticado.
5. POST exige papel admin.
6. O backend valida host `Noteri`, perfil NORMAL/ESTUDO e correlation_id.
7. Escrita deve ser atômica e seguida de leitura independente.
8. Repetir ESTUDO quando já ESTUDO deve retornar `changed=false`.
9. O E2E físico deve provar controle 401 sem autenticação, transição para ESTUDO,
   leitura independente por API/arquivo, replay idempotente e observação real na UI.
10. O runtime deve receber explicitamente o serviço same-origin e a `TaskConsoleView.vue`
    antes do teste, com confirmação dos fontes servidos pelo frontend.
11. O E2E deve exercitar ESTUDO → NORMAL → ESTUDO e terminar em ESTUDO.
12. Em falha após a fase de API, o reconciliador deve tentar restaurar ESTUDO antes
    do rollback dos arquivos de runtime.
13. HML e PROD não podem ser alterados.



## Critérios de aceite

1. O Task Console usa somente a API same-origin `/api/v1/noteri/profile` e não acessa `127.0.0.1:8765` pelo navegador.
2. GET sem autenticação retorna 401; POST exige administrador.
3. NORMAL → ESTUDO persiste no `host-profile.json` canônico e é confirmado por leitura independente da API e do arquivo.
4. Repetir ESTUDO quando já ESTUDO retorna `changed=false`, sem efeito duplicado.
5. O fluxo pela interface observa ESTUDO, volta a NORMAL, reaplica ESTUDO e confirma ESTUDO como estado final.
6. HML/PROD, segredos e exposição pública do agente loopback permanecem fora do escopo.
7. Erros HTTP não expõem caminhos, exceções internas ou outros detalhes sensíveis.

## Aplicação no runtime

A reconciliação deve ocorrer pelo runner self-hosted já autorizado do Noteri,
sem Remote Desktop/GUI, usando o projeto Docker DEV `reqsys-live`. O script
deve descobrir os binds e Compose reais pelos metadados Docker, manter backup
dos arquivos alterados e executar rollback em falha.
