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

O repositório atualmente precisa estar com `allow_auto_merge=true` para usar o auto-merge nativo do GitHub. Enquanto essa opção estiver desabilitada, o workflow atua como gate de elegibilidade para merge manual ou para automação externa governada.

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
├── runtime-health-validator.json
└── summary.md
```

Essas evidências devem ser usadas no status executivo para diferenciar:

- estado declarado;
- estado validado;
- estado evidenciado;
- estado consolidado.

## Próximo incremento recomendado

Após este gate estabilizar, evoluir para:

1. auditoria de branch protection;
2. label automática `merge-queue:eligible` quando todos os gates passarem;
3. habilitação explícita de `allow_auto_merge` no repositório, se a política permitir;
4. integração com dashboard operacional de PRs paralelos;
5. relatório executivo de capacidade segura de paralelismo por domínio.
