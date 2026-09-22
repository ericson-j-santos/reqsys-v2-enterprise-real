# Security Specialized Scanners — ReqSys

## Objetivo

Adicionar scanners especializados ao pipeline de segurança do ReqSys, complementando o `Security Baseline Gate` com ferramentas focadas em segredos, dependências, SBOM e SAST.

## Decisão

O baseline heurístico permanece como primeira barreira rápida e determinística. Os scanners especializados entram como segunda camada de profundidade.

A política operacional padrão é **report-only** para `pull_request` e `push`, evitando que backlog técnico ou falso positivo de scanner externo bloqueie a evolução antes de existir consolidador executivo de segurança. O bloqueio estrito fica disponível por execução manual com `workflow_dispatch` e `strict=true`.

## Scanners adicionados

| Scanner | Finalidade | Evidência |
|---|---|---|
| Gitleaks | Detecção especializada de segredos no snapshot atual do repositório | Summary/artifact do action |
| pip-audit | Vulnerabilidades em dependências Python | `pip-audit-report` |
| npm audit | Vulnerabilidades em dependências Node/frontend | `npm-audit-report` |
| Anchore SBOM | Inventário CycloneDX de componentes | `reqsys-sbom-cyclonedx` |
| CodeQL | SAST para Python e JavaScript/TypeScript | GitHub Code Scanning |

## Política de execução

O workflow executa em:

- `pull_request` para `main`;
- `push` em `main`;
- `workflow_dispatch` manual.

## Modo strict

O input `strict` controla se scanners suportados devem falhar o job quando houver achados.

```text
strict=false -> padrão; publica evidência sem bloquear CI/PR
strict=true  -> execução manual; falha quando scanner suportado retorna vulnerabilidade/risco
```

## Evidências geradas

```text
artifacts/security-scanners/
├── pip-audit/
├── npm-audit/
└── sbom/
```

Artifacts publicados:

- `pip-audit-report`
- `npm-audit-report`
- `reqsys-sbom-cyclonedx`

## Guardrails

- Sem deploy.
- Sem alteração funcional no runtime.
- Sem leitura manual de secrets.
- Permissões mínimas declaradas no workflow.
- Evidências preservadas por 30 dias.
- Scanners separados por job para facilitar diagnóstico.
- Bloqueio estrito somente sob execução manual intencional.

## Relação com o Security Baseline Gate

| Camada | Papel |
|---|---|
| Security Baseline Gate | Regras rápidas, determinísticas e governadas do ReqSys |
| Security Specialized Scanners | Ferramentas especializadas e relatórios técnicos complementares |

## Próximos incrementos recomendados

1. Consolidar os resultados dos scanners em um único `security-executive-summary.json`.
2. Expor score de segurança no Ops Dashboard.
3. Criar política formal de exceção temporária para vulnerabilidades aceitas.
4. Adicionar SARIF customizado para achados internos do baseline.
5. Bloquear deploy de produção quando houver crítico não mitigado.