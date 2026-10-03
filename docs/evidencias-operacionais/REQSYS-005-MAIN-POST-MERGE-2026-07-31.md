# Evidência canônica — REQSYS#005 pós-merge da main

## Identificação

| Campo | Valor |
|---|---|
| Frente | `REQSYS#005 • GOVERNANCA_CI • GATES_WORKFLOWS` |
| Captura | 31/07/2026 14:56 BRT |
| Repositório | `ericson-j-santos/reqsys-v2-enterprise-real` |
| Branch validada | `main` |
| SHA observado da `main` | `56e25dd35343d21b4fdc1774087de44cd4c45f97` |
| PR de origem | [#1139](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/1139) |
| SHA do PR validado | `2e0eeae36cde9582e583dbf61b0ce7f32e5c97c7` |
| Resultado | Evidência estrutural válida; consolidação pós-merge específica ainda pendente |

## Mudança consolidada

O PR #1139 removeu o gatilho duplicado `pull_request: closed` do workflow `Padrão Ouro Delivery Automation`, separou o grupo de concorrência por evento e branch e adicionou o `Padrão Ouro Delivery Queue Guard` para cancelar apenas execuções legadas ou comprovadamente substituídas.

O merge commit do PR corresponde ao SHA observado como HEAD da `main` no momento da captura:

```text
56e25dd35343d21b4fdc1774087de44cd4c45f97
```

Commit:

- https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/commit/56e25dd35343d21b4fdc1774087de44cd4c45f97

## Gates do SHA do PR

| Gate | Resultado | Run |
|---|---|---|
| CI — ReqSys v2 Enterprise | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385503 |
| CI Enterprise Fast | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385543 |
| Governance Quality Gates | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385556 |
| Governança Padrão Ouro | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385380 |
| PR Governed CI Validation | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385435 |
| PR Evidence Gate | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385525 |
| Branch Protection Audit | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385326 |
| Security Baseline Gate | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385641 |
| Merge Readiness Pareto Gate | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385713 |
| Governed Merge Queue | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385560 |
| PR Conflict Guard | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385345 |
| Artifact Contract Validation | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385426 |
| Security Specialized Scanners | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385549 |
| Test Quality Gate — Padrão Ouro | `success` | https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/30651385810 |

Na consulta realizada, 32 workflows associados ao SHA do PR estavam concluídos com `success`.

## Artifacts confirmados

| Artifact | ID | Digest | Expiração |
|---|---:|---|---|
| `pr-evidence-gate-2e0eeae36cde9582e583dbf61b0ce7f32e5c97c7` | `8801568958` | `sha256:0ccf628011364f7a43486d27295603a4945f1924cd63c2b97720739e2168f470` | 30/08/2026 |
| `merge-readiness-evidence` | `8801519648` | `sha256:0bcdd2a0a261020daccd7eb90fffdaf2115995785e2d37b1261013b358bb47a4` | 30/08/2026 |
| `branch-protection-audit` | `8801504010` | `sha256:48c6130858c77b16429dc5d43fe1cadd0430cc1a014ad919d232e026a46cdc9a` | 30/08/2026 |
| `security-baseline-report` | `8801511072` | `sha256:9509f469a73eb2edf75539f167d1cfc6992bc0d31b7082a7cc4ee1b4782339ed` | 30/08/2026 |

## Resultado da validação

### Evidenciado

- A `main` contém o merge commit do PR #1139.
- O SHA do PR foi aprovado pelos gates centrais de CI, governança, segurança, evidence e merge safety.
- Artifacts essenciais foram publicados com digest SHA-256 e não estavam expirados.
- A correção estrutural do deadlock está presente na `main`.

### Limitação atual

O conector utilizado na captura não retornou um conjunto de workflow runs diretamente associado ao merge commit `56e25dd35343d21b4fdc1774087de44cd4c45f97`. Portanto, esta evidência não declara que um run específico disparado por `push` na `main` concluiu com sucesso para esse SHA.

## Decisão

- Estado técnico da frente: **verde**.
- Maturidade consolidada: **96%**.
- Declaração de 100%: **bloqueada**.
- Motivo do bloqueio: ausência de URL e resultado de um run pós-merge específico da `main` para o SHA consolidado.

## Critério de fechamento

Para promover REQSYS#005 a 100%, anexar a esta evidência ou a uma evidência sucessora:

1. SHA da `main` contendo este incremento;
2. URL de run pós-merge concluído com `success`;
3. resultado dos checks críticos;
4. artifacts e digests aplicáveis;
5. confirmação de que não existe required check crítico falho ou pendente.

Até que isso ocorra, o merge isolado não deve ser tratado como evidência suficiente de consolidação.
