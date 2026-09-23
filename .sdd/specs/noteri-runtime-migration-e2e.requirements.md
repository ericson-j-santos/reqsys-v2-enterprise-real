# Noteri Runtime Migration E2E — requisitos

## Objetivo

Validar fisicamente, no host Noteri, o SHA exato do novo repositório
`ericson-j-santos/noteri-runtime` durante a migração incremental da Runtime Platform.

## Escopo

Este contrato é um harness operacional temporário de migração. Ele não altera
o runtime canônico do ReqSys e não deve ser integrado à `main`.

## Requisitos

1. A execução física DEVE ocorrer somente em runner com labels
   `[self-hosted, Windows, X64, noteri, reqsys-dev]`.
2. O alvo DEVE permanecer fixo em
   `ericson-j-santos/noteri-runtime@336e99a7fb7feb598d9be9aa2b143c3f9f87164e`.
3. O checkout DEVE comprovar o SHA observado antes do teste.
4. O E2E DEVE usar agente isolado, loopback-only e estado temporário, sem reutilizar
   o agente operacional previamente instalado.
5. O caso positivo DEVE comprovar `NORMAL -> ESTUDO -> NORMAL`.
6. O replay de `NORMAL` DEVE ser idempotente e retornar `changed=false`.
7. O controle negativo DEVE rejeitar host inválido com HTTP 409 e
   `host_target_mismatch`, sem alterar o estado.
8. A leitura independente do arquivo persistido DEVE confirmar estado final
   `NORMAL` e `accepts_new_development=true`.
9. O artifact DEVE registrar `correlation_id`, SHA alvo, host, resultado,
   controles, leitura independente e flags sanitizadas.
10. A execução NÃO DEVE ler segredos, tocar produção ou depender de RDC.
11. O workflow principal `noteri-control-plane-probe.yml` DEVE preservar seu
    comportamento original por `workflow_dispatch`; o job de migração só pode
    executar no branch operacional fixo.
12. Este harness NÃO DEVE ser mergeado na `main`; a evidência produzida deve ser
    vinculada à issue de migração e ao PR do novo repositório.

## Critérios de aceite

- checkout do SHA alvo: aprovado;
- E2E físico: aprovado;
- replay idempotente: aprovado;
- controle negativo: aprovado;
- leitura independente final: `NORMAL`;
- artifact sanitizado publicado;
- Pre-PR Readiness do branch operacional sem violações contratuais.
