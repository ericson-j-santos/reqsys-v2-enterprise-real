# ADR — Security Strong Guardrails

- **Data:** 2026-06-21
- **Status:** Proposto
- **Escopo:** ReqSys / CI / Governança / Segurança
- **PR:** #70

## Contexto

O ReqSys precisa impedir que configurações inseguras cheguem a `main` ou produção. Guardrails fracos, apenas documentais ou manuais, não são suficientes para o nível de maturidade enterprise esperado.

A política adotada deve bloquear evidências objetivas de risco crítico e registrar alertas auditáveis para endurecimento gradual da cadeia de entrega.

## Decisão

Implementar uma camada dedicada de **Security Strong Guardrails** executada em pull requests, pushes na `main` e execução manual.

A camada adiciona:

1. Workflow bloqueante `.github/workflows/security-strong-guardrails.yml`.
2. Scanner determinístico `scripts/security_strong_guardrails.py`.
3. Relatórios versionáveis como artefatos de CI em `security-reports/`.
4. Separação entre achados críticos bloqueantes e alertas não bloqueantes.

## Gates críticos bloqueantes

| Categoria | Gate | Política |
|---|---|---|
| Autenticação | Auth desligada | Bloqueia merge/deploy |
| Autenticação | Login demonstrativo habilitado | Bloqueia merge/deploy |
| CORS | Wildcard `*` | Bloqueia merge/deploy |
| JWT | Validação desligada | Bloqueia merge/deploy |
| TLS | Validação desligada | Bloqueia merge/deploy |
| Logging | Dump de ambiente | Bloqueia merge/deploy |

## Alertas não bloqueantes

| Categoria | Alerta | Ação esperada |
|---|---|---|
| Supply chain | Actions por tag de versão | Evoluir para pin por SHA nos workflows críticos |
| Permissões CI | Permissões `write` amplas | Justificar e reduzir escopo por job |

## Consequências

### Positivas

- Reduz risco de regressão de segurança.
- Torna a evidência auditável no CI.
- Mantém o PR em draft enquanto o gate não estiver validado.
- Evita alteração artificial de status de maturidade sem evidência real.

### Custos

- Pode revelar débitos existentes.
- Pode exigir correções prévias antes de liberar revisão/merge.
- Pode demandar calibragem incremental para reduzir falsos positivos.

## Rollback

Remover:

- `.github/workflows/security-strong-guardrails.yml`
- `scripts/security_strong_guardrails.py`
- `docs/adr/ADR-2026-06-21-security-strong-guardrails.md`
- `docs/governanca/SECURITY_STRONG_GUARDRAILS.md`
- `docs/releases/2026-06-21-security-strong-guardrails.md`

Não há alteração direta de runtime neste incremento.
