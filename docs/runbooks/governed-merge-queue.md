# Merge Queue Governada

## Objetivo

Implementar uma fila de merge governada para aumentar o número de PRs paralelos sem elevar o risco de conflito, regressão ou quebra silenciosa após merge.

Fluxo operacional:

```text
PR → validação isolada
   → integração temporária contra main
   → smoke runtime
   → gate de elegibilidade
   → merge queue / auto-merge governado
```

## Escopo implementado

O workflow `.github/workflows/governed-merge-queue.yml` adiciona três estágios objetivos:

| Estágio | Finalidade | Bloqueia merge quando falha |
|---|---|---:|
| Validação isolada | Executa guardrails, smoke Python e checks frontend quando aplicável | Sim |
| Integração temporária | Simula merge contra `main` em branch efêmera local do runner | Sim |
| Smoke runtime | Executa `runtime_health_validator.py` em modo `report_only` e publica evidência | Sim |

## Decisão governada

Um PR só é considerado elegível para a fila quando:

1. a validação isolada termina com sucesso;
2. a integração temporária contra `main` não apresenta conflito;
3. o smoke runtime gera evidência sem erro;
4. demais workflows obrigatórios do repositório continuam verdes;
5. não há mudança crítica não governada em contratos, secrets, branch protection ou bootstrap global.

## Auto-merge

**Observação crítica:** o repositório está com `allow_auto_merge=false`. O workflow detecta esse estado em runtime, publica `allow_auto_merge` em `policy.json` e **não** depende do auto-merge nativo do GitHub.

Enquanto `allow_auto_merge=false`:

- o gate continua validando isolamento, integração temporária e smoke runtime;
- PRs elegíveis recebem a label `merge-queue:eligible`;
- o merge segue via **Governed PR Automation** (`execute_merge=true` + label `governed-merge-approved`) ou merge manual após demais gates obrigatórios.

Quando a política permitir habilitar `allow_auto_merge=true` no repositório, o mesmo workflow já expõe `native_auto_merge_available` na evidência para evolução futura sem mudança de contrato.

## Política de paralelismo seguro

### Permitido com baixo risco

- observabilidade;
- dashboards e analytics;
- documentação viva;
- testes;
- runbooks;
- evidências operacionais;
- validações CI desacopladas.

### Controlado

- workflows principais;
- runtime bootstrap;
- dependências globais;
- shared contracts;
- autenticação/autorização;
- schema/openapi.

## Evidências

O workflow publica o artefato:

```text
artifacts/governed-merge-queue/
├── policy.json
├── runtime-health-validator.json
└── summary.md
```

### Campos decisórios de `policy.json`

| Campo | Significado |
|---|---|
| `eligible` | PR passou validação isolada + integração temporária |
| `allow_auto_merge` | Estado atual do repositório no GitHub |
| `native_auto_merge_available` | Espelho de `allow_auto_merge` para automação futura |
| `merge_path` | Caminho operacional recomendado (`governed_pr_automation`) |

Essas evidências devem ser usadas no status executivo para diferenciar:

- estado declarado;
- estado validado;
- estado evidenciado;
- estado consolidado.

## Labels automáticas

| Label | Quando aplicar | Quando remover |
|---|---|---|
| `merge-queue:eligible` | Gate `merge-queue-gate` com sucesso | Qualquer falha nos estágios anteriores |

A label **não** autoriza merge sozinha. Ela sinaliza elegibilidade técnica da fila governada; o merge continua exigindo CI obrigatório, label `governed-merge-approved` e disparo explícito de **Governed PR Automation** enquanto `allow_auto_merge=false`.

## Próximo incremento recomendado

Após este gate estabilizar, evoluir para:

1. auditoria de branch protection acoplada ao resultado de `policy.json`;
2. habilitação explícita de `allow_auto_merge` no repositório, se a política permitir;
3. integração com dashboard operacional de PRs paralelos;
4. relatório executivo de capacidade segura de paralelismo por domínio.
