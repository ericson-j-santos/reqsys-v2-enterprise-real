# E2E Platform — piloto Central Global

## Objetivo

Comprovar que o ReqSys pode permanecer dono de suas jornadas de negócio e consumir o repositório `ericson-j-santos/e2e-platform` apenas como infraestrutura transversal de validação de evidência.

## Requisitos

1. O E2E existente `runtime/scripts/e2e_central.py` continua sendo a fonte de verdade funcional.
2. O mesmo `correlation_id` deve ser usado pela execução real e pelo JSON de evidência.
3. A evidência deve usar o SHA completo do HEAD executado.
4. A execução deve comprovar caso positivo, controles negativos, idempotência e leitura independente.
5. Evidência só pode ser escrita após código de saída zero e presença de todos os marcadores obrigatórios do E2E real.
6. O workflow consumidor deve chamar `e2e-platform` por SHA completo e imutável.
7. O gate compartilhado deve falhar fechado para artifact ausente, estrutura inválida ou controle obrigatório falho.
8. Nenhum segredo, deploy ou ambiente de produção faz parte deste incremento.

## Critérios de aceite (Acceptance Criteria)

1. `runtime/tests/test_e2e_platform_central_pilot.py` aprova o contrato do adaptador e seu controle negativo.
2. O Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato e `behind_by=0`.
3. Na PR, o job `Central Global E2E real` executa a API real em memória e conclui com sucesso.
4. O artifact `central-e2e-evidence` contém `evidence.json`, `central-e2e.log` e `runtime.log`.
5. O job `E2E Platform Evidence Gate` usa `ericson-j-santos/e2e-platform/.github/workflows/e2e-evidence.yml@6ca2bf4e63af918872ab5b2b52485cb4f5f07314`.
6. O `platform_ref` informado ao gate é o mesmo SHA completo usado em `uses`.
7. A evidência final referencia o mesmo HEAD e `correlation_id` da execução real.
