# Schema Governance Gates

Atualizado em: 2026-06-24

## Objetivo

Impedir que contratos JSON, eventos, payloads de API e estruturas usadas por UI dinâmica evoluam sem versionamento, validação, rastreabilidade e evidência de CI.

Este gate transforma schema version JSON em capacidade governada da plataforma, não apenas em validação pontual de um domínio.

## Estado evidenciado

| Capacidade | Estado |
|---|---|
| Registry central de schemas | Implementado em `docs/schema-registry.json` |
| Validador transversal | Implementado em `tools/schema_governance/validate_schema_governance.py` |
| Validação por CI | Implementada em `.github/workflows/schema-governance-gate.yml` |
| Exemplo válido obrigatório | Governado por registry |
| Exemplo inválido obrigatório | Governado por registry |
| Detector base/head de breaking changes | Implementado para PRs |
| Artifact de evidência | `schema-governance-report` |

## Gates mínimos obrigatórios

| Gate | Regra |
|---|---|
| Schema Contract Gate | Todo contrato em `schemas/**/*.schema.json` deve ser JSON válido e registrado. |
| Schema Version Gate | Todo schema deve possuir `schema_version` obrigatório e com `const` SemVer. |
| Example Validation Gate | Cada contrato registrado deve declarar exemplos válidos e inválidos. |
| Breaking Change Gate | Mudança incompatível exige versão MAJOR e política `major_version_required`. |
| Additional Properties Gate | Objetos devem declarar `additionalProperties: false`. |
| Required Fields Gate | Campos obrigatórios precisam ser explícitos e versionados. |
| Enum Evolution Gate | Enum deve ser declarado de forma explícita para análise de impacto. |
| Contract Registry Gate | Schema novo sem entrada no registry bloqueia o CI. |
| CI Artifact Gate | Toda execução deve publicar relatório de evidência. |
| Runtime Validation Gate | Contrato crítico deve marcar `runtime_validation_required: true`. |

## Detector base/head

Em pull requests, o workflow executa:

```bash
python tools/schema_governance/validate_schema_governance.py --base-ref "origin/${{ github.base_ref }}"
```

O detector compara os schemas registrados no head do PR contra a versão existente na base do PR.

## Quebras detectadas

| Quebra | Ação exigida |
|---|---|
| Campo removido | `schema_version` com MAJOR maior |
| Campo obrigatório novo | `schema_version` com MAJOR maior |
| Tipo alterado | `schema_version` com MAJOR maior |
| Valor de enum removido | `schema_version` com MAJOR maior |
| `const` alterado, exceto `schema_version` | `schema_version` com MAJOR maior |
| Objeto removido | `schema_version` com MAJOR maior |
| `additionalProperties` relaxado | Bloqueado como quebra governada |

## Política de versionamento

| Tipo de mudança | Versão esperada |
|---|---|
| Correção sem quebra | PATCH |
| Campo opcional novo | MINOR |
| Novo enum compatível | MINOR com análise de impacto |
| Campo obrigatório novo | MAJOR |
| Remoção de campo | MAJOR |
| Alteração de tipo | MAJOR |
| Alteração de significado semântico | MAJOR |

## Como registrar um novo schema

1. Criar `schemas/<dominio>/<nome>.schema.json`.
2. Declarar `$schema`, `$id`, `title`, `type`, `required`, `properties` e `additionalProperties: false`.
3. Incluir `schema_version` obrigatório com `const` SemVer.
4. Criar pelo menos um exemplo válido.
5. Criar pelo menos um exemplo inválido.
6. Registrar o contrato em `docs/schema-registry.json`.
7. Executar `python tools/schema_governance/validate_schema_governance.py`.
8. Em PR, validar o comparativo base/head pelo workflow `Schema Governance Gate`.

## O que não pode passar batido

- Schema novo sem registry.
- Payload sem `schema_version`.
- Schema com objeto aberto sem justificativa.
- Exemplo válido quebrado.
- Exemplo inválido aceito indevidamente.
- Campo obrigatório novo sem versão MAJOR.
- Campo removido sem versão MAJOR.
- Enum removido sem versão MAJOR.
- Tipo alterado sem versão MAJOR.
- Runtime crítico sem validação obrigatória.
- Gate sem artifact de evidência.

## Limites atuais

- O detector não resolve `$ref` externo.
- O detector não executa validação JSON Schema completa; cobre o subconjunto governado usado atualmente pelo ReqSys.
- O detector compara apenas schemas registrados no registry.
- Mudanças semânticas que não alteram estrutura ainda exigem revisão humana.

## Próximo incremento recomendado

Adicionar testes automatizados do próprio gate com fixtures de quebra compatível/incompatível para provar que o detector bloqueia mudanças perigosas e permite mudanças compatíveis.
