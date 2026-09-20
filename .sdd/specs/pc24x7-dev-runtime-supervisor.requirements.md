# Requisitos — Supervisor autônomo do runtime DEV

## Objetivo

Eliminar ações humanas repetitivas da operação pública do ReqSys DEV no PC24x7.

## Requisitos funcionais

1. Recuperar containers DEV conhecidos quando estiverem parados.
2. Validar `/task-console` e `/api/health` antes e depois da reconciliação.
3. Reconciliar automaticamente os dois Cloudflare Quick Tunnels.
4. Detectar a capability do Tailscale Funnel sem abrir navegador repetidamente.
5. Ativar/reconciliar o Funnel automaticamente quando a capability já tiver sido concedida.
6. Enquanto o consentimento único não existir, manter Cloudflare operacional e registrar
   `TAILSCALE_FUNNEL_CONSENT_REQUIRED`.
7. Persistir estado e log fora do Git.
8. Executar periodicamente por Task Scheduler do usuário, sem privilégio elevado.
9. Não alterar HML ou PROD.

## Critérios de aceite

1. Testes comprovam escopo somente DEV e containers esperados.
2. Instalação cria tarefa recorrente `ReqSys-Dev-Runtime-Supervisor`.
3. Supervisor local conclui com gateway DEV saudável.
4. Cloudflare continua respondendo HTTP 200.
5. Ausência da capability Funnel não derruba DEV nem abre consentimento em loop.
6. Após concessão da capability, o Funnel passa a ser reconciliado automaticamente.
