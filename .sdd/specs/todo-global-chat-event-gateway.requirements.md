# Gateway ChatGPT → TODO Global por TodoEvent v1

## Objetivo

Permitir que o ChatGPT publique TODOs no fluxo canônico do TODO Global sem receber
segredos, sem terminal local/remoto e sem interpretar texto de TODO como comando.

A entrada governada é um comentário na issue operacional #1705 com o prefixo
`/reqsys todo-event-v1 ` seguido de um TodoEvent v1 codificado em base64url.

## Requisitos

1. O workflow deve aceitar somente comentários criados na issue #1705 pelo ator
   `ericson-j-santos`.
2. A mensagem deve começar exatamente por `/reqsys todo-event-v1 `.
3. O payload deve ser base64url contendo um objeto TodoEvent v1.
4. O produtor deve ser `chatgpt`.
5. Campos top-level e campos de `todo` fora da allowlist devem ser rejeitados.
6. Campos como `automation_action` ou `execution_request` nunca podem ser
   aceitos nem executados.
7. O payload do comentário nunca deve ser interpolado em shell.
8. O workflow deve usar OIDC existente, resolver o locator DEV assinado e ler o
   token do produtor no Key Vault sem persistir seu valor.
9. Antes da publicação, o ReqSys público e o TODO Runtime público devem declarar
   o mesmo SHA de `github.sha`.
10. A publicação deve executar o controle negativo do endpoint.
11. Após aceitação, deve aguardar estado terminal com `readback_verified=true`.
12. O mesmo `event_id` deve ser reenviado e retornar o mesmo `job_id` com
    `duplicate_event=true`.
13. A evidência persistida deve conter somente identificadores e resultados
    sanitizados; nenhum segredo.
14. O fluxo é DEV e não toca produção.
15. As Actions usadas pelo novo workflow devem ser fixadas por SHA completo.

16. O bootstrap do contrato deve instalar explicitamente pytest e PyYAML, incluindo\n    as dependências dos dois módulos de teste executados no job isolado.\n17. O produtor deve iniciar por módulo Python a partir da raiz do repositório, sem\n    depender de PYTHONPATH herdado para importar o pacote scripts.\n\n## Critérios de aceite

- teste positivo valida extração e publicação de um evento autorizado;
- ator ou issue divergente falham fechado;
- campos de execução não allowlisted falham fechado;
- TODO bloqueado sem `blocker` e `next_action` falha fechado;
- controle negativo, readback e replay idempotente são obrigatórios;
- o workflow não usa `pull_request_target`, `eval` ou conteúdo do comentário
  como shell;
- `Pre-PR Readiness Gate` retorna `READY_FOR_PR=passed` no HEAD exato;
- E2E pós-merge publica um TodoEvent real, confirma estado terminal,
  leitura independente e replay sem segundo job.

## Regressão pós-merge de 2026-09-28

O run 36421507066, no SHA fa8eef53ff50075cc8949a050434b470b0dda28f,
falhou antes de autenticar: os testes do ciclo horário importam yaml, mas o
job do chat instalava apenas pytest. O gate pré-PR possuía PyYAML no ambiente
e não detectou essa diferença. A correção declara a dependência no próprio
job, testa a ausência de YAML e valida o ponto de entrada sem PYTHONPATH.
O E2E externo continua pendente até locator e runtime no mesmo SHA.
