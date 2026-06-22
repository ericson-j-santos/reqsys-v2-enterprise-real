# ADRs Genéricos — ReqSys

**Status:** Proposto para adoção como base canônica de ADRs genéricos.
**Data:** 2026-06-22
**Contexto:** ReqSys, GovBI, RAG, Runtime Center, automações, integrações e plataforma corporativa.

---

## Objetivo

Este diretório centraliza um conjunto genérico e reutilizável de ADRs para decisões recorrentes de arquitetura, segurança, governança, IA, observabilidade, frontend analítico, integração e operação autônoma.

O pacote completo também foi publicado como HTML autocontido no Google Drive:

- Google Drive: https://drive.google.com/file/d/1HGHEX99N2NkLh1QlezLw7un-lKbXsU7R/view?usp=drivesdk

---

## ADRs previstos

| ADR | Tema | Status sugerido |
|---|---|---|
| ADR-000 | Template de decisão arquitetural | Proposto |
| ADR-001 | Arquitetura Hexagonal e Camadas | Aceito |
| ADR-002 | LGPD, PII, Segredos e Mascaramento | Aceito |
| ADR-003 | Auditoria, Correlação e Rastreabilidade | Aceito |
| ADR-004 | Autenticação, JWT e RBAC | Aceito |
| ADR-005 | Segregação de Ambientes e Gates de Produção | Aceito |
| ADR-006 | CI/CD, Quality Gates e Pull Requests | Aceito |
| ADR-007 | Observabilidade, Telemetria e Runtime Health | Aceito |
| ADR-008 | IA Governada, RAG, Fontes e Explainability | Aceito |
| ADR-009 | Frontend Schema-Driven UI, Analytics e Drill-down | Aceito |
| ADR-010 | Integrações, Adapters, Resiliência e Timeouts | Aceito |
| ADR-011 | Operação Autônoma, Remediação Governada e Guard Rails | Proposto |
| ADR-012 | Documentação Viva, Arquitetura Viva e Relatórios HTML | Aceito |

---

## Convenção de status

| Status | Uso |
|---|---|
| Proposto | Ainda em avaliação |
| Aceito | Decisão aprovada para uso |
| Implementado | Decisão aplicada e validada |
| Substituído | Decisão trocada por outra |
| Deprecated | Não deve ser usada em novas entregas |

---

## Regras de governança

- Toda decisão arquitetural relevante deve possuir ADR.
- Todo ADR deve ser versionado.
- Mudança crítica deve atualizar README e CHANGELOG.
- Produção deve ser bloqueada quando violar gates de segurança.
- Relatórios HTML devem ser autocontidos sempre que aplicável.
- Evidências devem vir de CI, testes, logs, prints, artefatos ou validação objetiva.
- O estado atual evidenciado deve ser separado do estado alvo desejado.

---

## Próximos incrementos recomendados

1. Materializar cada ADR em arquivo Markdown individual neste diretório.
2. Adicionar workflow para validar nomenclatura e status dos ADRs.
3. Publicar relatório HTML autocontido como artefato de documentação.
4. Vincular ADRs aos PRs e issues correspondentes.
