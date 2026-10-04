# Movimento Email — roteamento automático da origem em DEV

## Objetivo
Eliminar o bloqueio operacional de desenvolvimento quando a origem SQL corporativa não estiver configurada ou não resolver DNS, sem transformar a equivalência DEV em evidência corporativa.

## Requisitos
1. Suportar os modos `auto`, `corporate` e `equivalent-dev`.
2. Em `corporate`, qualquer ausência de DSN, DNS indisponível, falha de autenticação, contrato ou SQL deve permanecer fail-closed.
3. Em `auto`, usar a equivalência DEV somente quando a configuração corporativa estiver ausente ou o host corporativo não resolver DNS.
4. Configuração ambígua (variável + arquivo simultaneamente) deve bloquear, nunca cair para fallback.
5. DSN presente porém inválido deve bloquear, nunca cair para fallback.
6. Após selecionar corporate, falhas posteriores não podem ser mascaradas pela equivalência.
7. A equivalência deve continuar registrando `equivalent_source=true`, `synthetic=true` e `corporate_source_validated=false`.
8. A rota corporativa somente pode registrar `corporate_source_validated=true` após dry-run, apply e repetição noop aprovados.
9. Nenhum DSN, segredo ou linha de negócio pode ser escrito na evidência.
10. Produção permanece desabilitada.

## Critérios de aceite
1. Sem DSNs, `--mode auto` seleciona `equivalent-dev` com motivo `corporate_dsn_configuration_missing`.
2. Em `--mode corporate`, a mesma ausência bloqueia.
3. Com DSNs válidos mas DNS indisponível, `auto` usa equivalência e `corporate` bloqueia.
4. DSN ambíguo ou inválido nunca usa fallback.
5. Com origem pronta, `auto` seleciona corporate sem fallback.
6. O E2E atual do Noteri deve passar pela equivalência com repetição idempotente e views `2/1/1/1`.
7. Testes direcionados e Pre-PR Readiness devem passar no HEAD exato.
