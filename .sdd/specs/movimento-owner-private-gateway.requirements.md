# Movimento Owner Private Gateway

## Objetivo

Criar uma rede privada autogerida entre os hosts ReqSys para acesso à fonte owner-managed sem expor o SQL Server diretamente e sem depender de equipe ou infraestrutura externa.

## Requisitos

1. O SQL Server deve permanecer acessível localmente em `localhost:1433`.
2. O gateway deve bindar somente em IPv4 do overlay `100.64.0.0/10`; loopback é permitido apenas para testes.
3. Endereços públicos e RFC1918/LAN não podem ser usados como bind automático.
4. O nome lógico estável é `reqsys-owner-data-gateway`.
5. O gateway deve exigir bearer token para `/status`, `/ingest` e `/sync`.
6. O token deve existir fora do Git e nunca aparecer em logs/evidências.
7. `/health` não deve expor segredo ou conteúdo de negócio.
8. A ingestão continua validando exatamente os quatro datasets owner-managed.
9. A sincronização remota só pode atingir `ReqSysMovimentoDev`.
10. O runtime deve ser copiado para `%LOCALAPPDATA%\ReqSys\OwnerGateway` e registrar auto-start no HKCU.
11. O bootstrap deve ser idempotente e reutilizar token existente.
12. PROD permanece desabilitado.

## Critérios de aceite

1. Detecção automática encontra um endereço do overlay `100.64.0.0/10` no Noteri.
2. O bootstrap retorna `status=passed`, `autostart=true` e `secrets_exposed=false`.
3. O endpoint `/health` responde com `logical_name=reqsys-owner-data-gateway`.
4. O endpoint `/status`, autenticado, confirma as quatro views da fonte e alvo.
5. Segunda execução do bootstrap não cria novo token e mantém o serviço saudável.
6. O gateway recusa bind automático em endereço LAN/público.
7. A suíte de testes da fonte e do gateway passa integralmente.
8. O Pre-PR Readiness passa no HEAD exato com `behind_by=0`.
9. Nenhuma ação toca PROD.
10. A integração com o Desktop pode ficar pendente apenas enquanto o host estiver fisicamente offline; quando online, o mesmo cliente deve usar o nome lógico e token provisionado.
