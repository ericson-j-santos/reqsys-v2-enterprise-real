# Branch Protection Audit — Evidência Executiva

## Estado evidenciado

| Item | Estado |
|---|---|
| Baseline versionada | `docs/governance/branch-protection-enterprise-baseline.md` |
| Auto-merge nativo | Habilitado no repositório |
| Merge Queue Governada | Implementada |
| Evidência de ruleset/branch protection via API | Pendente |
| Risco atual | Médio |
| Risco alvo | Baixo |

## Checks mínimos recomendados

- `Governança Padrão Ouro`
- `Governance Quality Gates`
- `CI — ReqSys v2 Enterprise`
- `CI Enterprise Fast`
- `Branch Protection Audit`
- `Governed Merge Queue`

## Política recomendada

- Pull request obrigatório antes do merge.
- Branch atualizada antes do merge.
- Conversas resolvidas.
- Aprovação mínima e stale approvals descartadas.
- Bloqueio de force push e deleção.
- Squash merge como caminho preferencial.
- Auto-merge permitido somente após checks obrigatórios verdes.

## Lacuna registrada

A aplicação efetiva do ruleset ainda precisa ser confirmada diretamente nas configurações do GitHub ou por workflow/API dedicado com permissão administrativa.

## Próximo incremento recomendado

Criar integração com dashboard operacional para exibir maturidade de branch protection, checks obrigatórios e capacidade segura de PRs paralelos.
