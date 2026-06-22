# Guards de Produção — SQL Visual Explain

## Objetivo

Evitar que análise automática de SQL gere risco operacional, vazamento de informação ou execução indevida em ambiente produtivo.

## Bloqueios obrigatórios

| Guard | Regra |
|---|---|
| Ambiente | `EXPLAIN ANALYZE` não deve rodar em produção sem aprovação explícita |
| Credenciais | Connection strings, tokens e senhas não podem ser versionados |
| Dados sensíveis | PII/LGPD não pode aparecer em relatórios, exemplos ou logs |
| Query pesada | Consultas sem limite ou com alto custo exigem análise prévia |
| Escrita acidental | Apenas `SELECT` deve ser permitido no fluxo de explain automatizado inicial |
| Auditoria | Toda execução futura deve registrar `correlation_id` |

## Critério de maturidade

A solução só pode ser considerada avançada quando houver:

- Parser robusto com SQLGlot.
- Testes cobrindo CTE, subquery, agregações e múltiplos joins.
- CI validando geração dos relatórios.
- Execução segura de `EXPLAIN` com bloqueios por ambiente.
- Evidência versionada de execução.
