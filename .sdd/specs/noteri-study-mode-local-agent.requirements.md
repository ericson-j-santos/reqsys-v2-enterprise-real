# Modo ESTUDO do Noteri — canal local governado

## Requisito 1 — menor privilégio
O Task Console deve alterar o perfil do Noteri por um agente local dedicado, sem expor shell, execução genérica, porta remota ou credencial no frontend.

## Requisito 2 — estado canônico
O agente deve usar o mesmo contrato de `host-profile.json`: somente `NORMAL` ou `ESTUDO`, gravação atômica, `correlation_id` e `accepts_new_development` derivado do perfil.

## Requisito 3 — falha fechada
O agente deve escutar apenas em loopback, validar origem, rejeitar host diferente do Noteri, perfil inválido e `correlation_id` inválido.

## Requisito 4 — evidência
Após uma alteração, o Task Console deve executar nova leitura do agente e somente apresentar sucesso quando o arquivo lido confirmar o perfil e a capacidade esperada.

## Requisito 5 — experiência de uso
O Task Console deve mostrar o estado atual do Noteri e fornecer ações claras para ativar `ESTUDO` ou voltar a `NORMAL`. Quando o agente local estiver indisponível, a tela deve permanecer utilizável e indicar que a mudança de perfil está indisponível.

## Requisito 6 — acesso do runtime oficial local
O agente deve aceitar o Task Console oficial servido em `http://127.0.0.1:8083` ou `http://localhost:8083` sem ampliar a política para origens não locais, curingas ou hosts externos.

## Requisito 7 — inicialização sem tela branca
O frontend deve montar a interface antes de iniciar autenticação silenciosa externa. Uma falha ou demora do MSAL não pode manter o usuário em tela branca; a rota protegida deve permanecer no login e retornar ao destino original após autenticação válida.

## Critérios de aceite (Acceptance Criteria)
1. `scripts/noteri_host_profile_agent.py` não aceita bind externo a loopback.
2. O agente aceita `NORMAL|ESTUDO`, grava de forma atômica e registra auditoria sem segredos.
3. Testes negativos cobrem origem, host, perfil e `correlation_id` inválidos.
4. Repetir a mesma mudança é idempotente e retorna `changed=false`.
5. O serviço frontend executa POST seguido de GET e falha quando a leitura independente diverge.
6. O Task Console não declara que o Desktop assumiu uma tarefa sem evidência; informa apenas que o Noteri deixou de aceitar novas tarefas de desenvolvimento.
7. O E2E local comprova `NORMAL → ESTUDO → NORMAL` no Noteri real e restaura `NORMAL` ao final.
8. O Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato antes da abertura da PR.
9. `DEFAULT_ORIGINS` inclui explicitamente `http://127.0.0.1:8083` e `http://localhost:8083`.
10. A inclusão do runtime `8083` não permite origens externas nem remove a validação estrita de `Origin`.
11. O app monta antes do bootstrap MSAL assíncrono e mantém a proteção das rotas privadas pelo router guard.
12. `frontend/index.html` contém fallback visível para falha de bootstrap, evitando página totalmente branca quando o bundle não monta.
