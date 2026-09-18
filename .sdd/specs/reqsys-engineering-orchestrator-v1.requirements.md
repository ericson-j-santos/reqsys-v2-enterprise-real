# Requisitos — ReqSys Engineering Orchestrator v1.0.0

## Escopo

Adicionar uma camada canônica de contrato e roteamento de engenharia sobre o Operational Orchestrator já existente, sem criar fila, ledger ou executor paralelo.

## Requisitos funcionais

1. Rotear solicitações de planejamento para `planner`.
2. Rotear implementação/correção de código para `builder`.
3. Rotear falhas de CI/CD para `ci_remediator`.
4. Rotear validações E2E e controles contra falso positivo para `e2e_validator`.
5. Rotear merge, deploy de produção, force-push e demais ações críticas para `human_gate`.
6. Priorizar `human_gate` sobre qualquer rota mutável concorrente.
7. Preservar `correlation_id`, vínculo de evidência ao SHA e invalidação de evidência afetada após mudança de SHA.
8. Manter Builder e Validator separados quando o ambiente permitir.
9. Falhar fechado sem autorização, estado atual ou evidência obrigatória.
10. Reutilizar o Operational Orchestrator existente como ponte de runtime, sem duplicação do núcleo.
11. Manter `.reqsys-agent.json` em `safe-readonly` e preservar os bloqueios de merge, push, produção, exclusão, leitura de segredos e auto-remediação.
12. Não liberar produção, merge ou deploy neste incremento.

## Critérios de aceite

- validador estrutural retorna `status=passed`;
- casos de roteamento cobrem CI, implementação, E2E e planejamento;
- casos críticos cobrem merge, deploy de produção e force-push;
- controle negativo remove `human_gate` e deve falhar;
- duas execuções do validador produzem o mesmo resultado;
- JSON/YAML do pacote são válidos;
- `Pre-PR Readiness Gate` fica verde no HEAD exato;
- branch permanece `behind_by=0` antes de abrir PR.

## Fora do escopo

- habilitar auto-remediação;
- alterar executor produtivo;
- merge;
- deploy;
- mutação de segredos;
- permissões administrativas.
