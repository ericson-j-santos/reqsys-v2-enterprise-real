# Movimento Email — fonte equivalente DEV persistente

## Objetivo
Criar uma origem SQL local e persistente, contratualmente equivalente à origem legada da Prospecção Movimento, para permitir E2E fonte → camada canônica → views V2 quando a rede SQL corporativa não estiver disponível.

## Requisitos
1. Executar somente em `localhost`/loopback.
2. Exigir bancos com sufixo `Dev`.
3. Criar/reutilizar `ReqSysMovimentoSourceDev` e schema `legacy_ssrs`.
4. Preservar o alvo canônico `ReqSysMovimentoDev.movimento_src`.
5. Sincronizar os quatro datasets com fingerprint SHA-256 e repetição idempotente.
6. A segunda execução deve retornar `noop` e `already_present_no_write=true`.
7. Validar independentemente as quatro views V2.
8. Não criar login, usuário, segredo ou permissão administrativa.
9. Toda evidência deve registrar `equivalent_source=true`, `synthetic=true` e `corporate_source_validated=false`.
10. Nunca apresentar a equivalência DEV como prova da origem corporativa.

## Critério de conclusão
O comando `python scripts/movimento_email_equivalent_dev.py run` deve executar bootstrap → sync → repetição → validação das views com estado final `passed`, sem tocar produção.
