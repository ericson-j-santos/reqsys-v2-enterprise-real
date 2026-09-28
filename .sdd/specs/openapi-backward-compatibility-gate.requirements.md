# OpenAPI Backward Compatibility Gate — Requisitos

## Objetivo

Bloquear no CI mudanças incompatíveis de alta confiança entre o contrato OpenAPI
canônico da branch base e o contrato candidato do HEAD, antes do merge.

## Requisitos

1. O gate deve comparar o contrato canônico mais recente da base com o contrato canônico mais recente do HEAD.
2. Remoção de path ou operação HTTP existente deve bloquear.
3. Introdução de parâmetro obrigatório ou request body obrigatório deve bloquear.
4. Remoção de resposta declarada deve bloquear.
5. Remoção de schema/propriedade, alteração de tipo, novo campo obrigatório ou redução de enum deve bloquear.
6. Mudanças aditivas opcionais devem permanecer compatíveis.
7. O relatório JSON deve registrar SHA do HEAD quando disponível, entradas comparadas e lista objetiva das incompatibilidades.
8. Erro de leitura ou JSON inválido deve falhar fechado.
9. O workflow existente OpenAPI Routes Drift deve hospedar o gate; nenhum workflow adicional deve ser criado.
10. O controle negativo deve introduzir uma incompatibilidade conhecida e provar exit code diferente de zero.
11. Nenhum deploy, segredo, produção ou alteração de dados faz parte deste incremento.

## Critérios de aceite

- Testes unitários aprovam caso compatível e casos incompatíveis.
- O controle negativo do CLI bloqueia uma operação removida.
- O workflow publica artifact do relatório mesmo em falha.
- Pre-PR Readiness retorna READY_FOR_PR=passed no HEAD exato e behind_by=0 antes da abertura da PR.
- Na PR, o job de compatibilidade roda no SHA atual e não é skipped quando os arquivos de contrato/gate são alterados.
