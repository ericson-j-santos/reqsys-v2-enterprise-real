# Quality Gates

Codigo: AI-GOV-DEVOPS-001

## Decisao

Nenhuma alteracao deve seguir para producao sem validacao minima de qualidade.

## Gates obrigatorios

- Build concluido.
- Testes automatizados aprovados.
- Trilha D — Qualidade e Governanca (padrao ouro) verde no head SHA do PR.
- Revisao de PR concluida.
- Configuracoes por ambiente revisadas.
- Documentacao atualizada.
- Changelog atualizado quando houver impacto funcional.
- Riscos e rollback descritos quando aplicavel.

## Fluxo recomendado

1. Planejar.
2. Versionar.
3. Implementar.
4. Testar.
5. Validar CI.
6. Revisar.
7. Publicar.
8. Monitorar.
9. Documentar.
10. Evoluir.

## Referencias cruzadas

- docs/ai-governance/00_PRIORITY_RULES.md
- docs/ai-governance/09-CHECKLISTS/PR_CHECKLIST.md
- ReqSys: PRs devem permanecer em draft ate CI verde.