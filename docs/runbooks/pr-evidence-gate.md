# PR Evidence Gate — Runbook Operacional

## Objetivo

Garantir que nenhum PR seja considerado pronto, verde, resolvido ou apto para merge sem evidência objetiva no commit head atual.

## Estado evidenciado exigido

| Regra | Evidência mínima | Status alvo |
|---|---|---|
| Head commit validado | `pr.head.sha` capturado no workflow | Verde |
| Workflow run associado ao head atual | Runs consultados por `head_sha` | Verde |
| Checks obrigatórios executados | Workflows obrigatórios com `conclusion=success` | Verde |
| Artifact de auditoria presente | Artifact com `evidence` ou `artifact` no nome | Verde |
| Drift detectado | Falha quando não há run para o SHA atual | Verde |
| Auditoria rastreável | `audit/pr-evidence-gate.json` publicado como artifact | Verde |

## Workflows obrigatórios iniciais

- `CI — ReqSys v2 Enterprise`
- `Governance Quality Gates`
- `Governança Padrão Ouro`
- `PR Evidence Gate`

## Workflows opcionais monitorados

- `NGINX Security Profile`

O NGINX Security Profile é tratado como opcional no gate inicial porque possui filtros de caminho. Ele deve virar obrigatório na branch protection quando a política de paths e required checks estiver consolidada.

## Como interpretar o semáforo

| Cor | Estado | Ação |
|---|---|---|
| Verde | Runs obrigatórios no head atual, sucesso e artifact presente | Pode seguir para revisão humana |
| Amarelo | Evidência parcial, artifact ou workflow opcional ausente | Revalidar antes de avançar |
| Laranja | Workflow obrigatório ausente ou pendente no SHA atual | Rerun ou correção objetiva |
| Vermelho | Sem workflow run no SHA atual ou gate crítico falhou | Bloquear avanço |

## Restrições operacionais

- Não marcar ready for review sem CI completo verde.
- Não fazer merge sem revisão concluída e autorização explícita.
- Não declarar correção pronta sem validar logs, jobs e artifacts do head atual.
- Não tratar estado alvo como estado evidenciado.

## Próximos incrementos

1. Adicionar esse workflow à branch protection.
2. Tornar artifacts de evidência padrão em todos os workflows críticos.
3. Publicar painel consolidado de governança operacional.
4. Adicionar comentário automático seguro apenas quando o token tiver permissão adequada.
