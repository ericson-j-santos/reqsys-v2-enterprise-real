# Parallel Development Acceleration

Versão: `0.1.0`  
Data: `2026-06-29`  
Modo: `governado`, `baixo conflito`, `read-only first`

## Objetivo

Aumentar a vazão de incrementos paralelos no ReqSys sem elevar o risco operacional, evitando colisões em arquivos críticos, runtime produtivo, contratos compartilhados e dashboards HTML grandes.

## Política de paralelismo

| Tipo de incremento | Paralelismo | Critério |
|---|---|---|
| Runbooks e documentação | Seguro | Não altera runtime nem CI crítico |
| Dados estáticos versionados | Seguro com contrato | Exige JSON com `schema_version` e validador |
| Validadores read-only | Seguro | Sem rede, sem credenciais e sem mutação |
| Workflows de validação local | Controlado | Apenas `contents: read` e timeout curto |
| Runtime/API/Auth | Serial | Exige uma frente ativa por vez |
| HTML principal de dashboard | Serial ou patch pequeno | Evitar reescrita completa |

## Lanes recomendadas

1. `docs_runbooks_lane`
   - documentação operacional;
   - ADRs/runbooks;
   - índices executivos.

2. `ops_data_lane`
   - JSONs de dashboard;
   - burndown;
   - governance index;
   - snapshots report-only.

3. `validator_scripts_lane`
   - scripts `validate_*.py`;
   - testes locais;
   - validação sem dependência externa.

4. `workflow_validation_lane`
   - workflows pequenos;
   - `contents: read`;
   - sem deploy;
   - sem secrets.

## Regras para abrir PR paralelo

- Cada PR deve alterar preferencialmente até 3 arquivos.
- Cada PR precisa ter validador dedicado ou reutilizar gate existente.
- PRs paralelos não devem alterar o mesmo arquivo.
- Mudanças em `.github/workflows/*deploy*` devem ser serializadas.
- Mudanças em auth/runtime/API devem aguardar fila governada.
- Links só devem ser apresentados após CI próprio verde ou status evidenciado.

## Próximo incremento natural

Renderizar `parallel-safe-lanes-governance.json` no Ops Dashboard após merge do índice base.