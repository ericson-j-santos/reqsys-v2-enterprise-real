# Desktop control plane — atuador HTTP DEV estreito

## Objetivo

Permitir que o gateway ReqSys DEV já alcançável em `DESKTOP-PDQK954:8083`
solicite recuperação do plano de controle sem criar shell remoto, proxy genérico
ou novo executor privilegiado dentro da API.

## Arquitetura

`POST /api/internal/desktop-control-plane/recover` atua somente como adaptador
autenticado para o broker host-side já versionado em
`ericson-j-santos/desktop-pc24x7-runtime#2`.

O único comando emitido é exatamente:

`/desktop-runtime admin recover-control-plane`

O efeito privilegiado permanece responsabilidade do broker local do Desktop,
que já possui allowlist, anti-replay e handlers fixos.

## Guardrails

1. Ambiente permitido: somente local/DEV.
2. Endpoint exige `require_admin`.
3. Não aceita action, command, host, URL, path, executable ou argumentos arbitrários.
4. Repositório, issue, ator esperado e comando são constantes.
5. Usa somente o token GitHub já provisionado; nunca retorna ou registra o valor.
6. Antes de criar comentário, reutiliza um comando exato/fresco do owner dentro
   da janela de 240 segundos, reduzindo duplicidade em retries.
7. Comentário editado, ator divergente, associação diferente de OWNER, corpo
   divergente ou comentário antigo não serve para idempotência.
8. Não executa subprocess, PowerShell, CMD, WMI, SCM, Task Scheduler remoto, C$,
   WinRM, SSH, RDC, reboot ou produção.
9. A resposta HTTP 202 comprova somente aceitação no canal; recuperação funcional
   continua condicionada à evidência independente do broker/runner no Desktop.

## Critérios de aceite

- testes positivos e negativos passam no HEAD exato;
- Pre-PR Readiness passa com branch atualizada;
- rota está presente no OpenAPI do backend;
- chamada autenticada em DEV cria ou reutiliza somente o comando allowlisted;
- chamada em ambiente não DEV falha antes de qualquer transporte;
- nenhuma evidência declara o Desktop recuperado apenas por HTTP 202.
