# Foco Padrão Ouro — Plano de Execução Prioritária

Data de referência: 2026-06-29

Este foco operacional traduz o hub Padrão Ouro em uma sequência curta de execução para agentes e automações quando a prioridade explícita for elevar qualidade, rastreabilidade e prontidão de merge sem abrir frentes paralelas desnecessárias.

## Objetivo

Concentrar cada incremento em uma melhoria pequena, verificável e conectada aos artefatos Tier 1, evitando dispersão entre documentação, CI, produto e governança.

## Ordem de prioridade

| Prioridade | Frente | Resultado esperado | Evidência mínima |
| --- | --- | --- | --- |
| P0 | CI e segurança | Gates obrigatórios reproduzíveis e sem regressões conhecidas | Comandos locais ou link do workflow verde |
| P1 | Arquitetura viva | Índices, contratos e ownership atualizados junto do código | `README.md`, `LIVING_ARCHITECTURE_INDEX.md` ou JSON sincronizado |
| P2 | Testes críticos | Cobertura focada nos fluxos de maior risco | `pytest`, `npm run build`, Playwright ou justificativa |
| P3 | Evidência operacional | Artifacts, runbooks e dashboards navegáveis | Evidência em `docs/evidence/` ou artifact canônico |
| P4 | Experiência do usuário | Telas recentes com feedback claro e responsivo | Screenshot, vídeo ou E2E responsivo quando aplicável |

## Loop operacional

```text
1. Triar o pedido e identificar se é correção, consolidação ou nova frente.
2. Consultar o Living Architecture Index e respeitar ownership/boundaries.
3. Executar o menor diff que aumente prontidão Padrão Ouro.
4. Validar com o teste mais próximo do risco alterado.
5. Registrar evidência no PR com escopo, fora de escopo, riscos e rollback.
```

## Definition of Done Padrão Ouro

Um incremento só deve ser considerado pronto quando cumprir todos os itens aplicáveis:

- Escopo mínimo e rastreável, sem mudanças oportunistas.
- Contratos, índices ou runbooks atualizados quando a mudança afetar arquitetura, operação, segurança ou testes.
- Teste local executado ou limitação ambiental documentada.
- Risco e rollback descritos no PR.
- Nenhum segredo, banco local modificado ou artefato temporário incluído no commit.

## Anti-distrações

Evitar durante um foco Padrão Ouro:

- Criar nova frente quando uma consolidação ativa resolve o risco atual.
- Atualizar documentação sem apontar para comandos, artefatos ou owners verificáveis.
- Misturar refactor amplo com correção pontual de CI.
- Usar screenshots como única evidência para mudanças de backend, segurança ou contrato.
- Considerar PR pronto sem E2E responsivo quando a alteração impactar tela ou navegação.

## Mapeamento rápido

| Se o pedido mencionar... | Comece por... |
| --- | --- |
| “padrão ouro”, “consolidar”, “foco” | Este plano + `ENGINEERING_PLAYBOOKS.md` |
| “arquitetura”, “owner”, “módulo” | `LIVING_ARCHITECTURE_INDEX.md` + `living-architecture-index.json` |
| “teste”, “cobertura”, “CI” | `TESTING_PLAYBOOK.md` |
| “evidência”, “artifact”, “runtime” | `RUNTIME_EVIDENCE_GRAPH.md` |
| “contrato”, “schema”, “payload” | `CONTRACT_CATALOG.md` |

## Modo consolidação (`state_yellow`)

Quando o coordenador estiver em `state_yellow` (`new_front_allowed: false`), o foco muda para estabilização:

| Tipo permitido | Quando usar |
| --- | --- |
| `consolidate` | Concluir CI/evidência/merge de incremento já aberto |
| `gap_fix` | Corrigir gap documentado com escopo fechado (`OPS-GAP-*`) |
| `hotfix` | Correção urgente e mínima com referência explícita |

Neste modo, evite abrir frente paralela. Feche PRs duplicados apontando para o canônico em `main`.

## Comando de triagem recomendado

Para nova frente, executar antes de alterar código:

```bash
python3 scripts/agent_increment_gate.py --increment-type new_front --intent "foco padrao ouro"
```

Quando a mudança for consolidação, correção de gap ou hotfix, usar o tipo correspondente:

```bash
python3 scripts/agent_increment_gate.py --increment-type consolidate --intent "foco padrao ouro"
```
