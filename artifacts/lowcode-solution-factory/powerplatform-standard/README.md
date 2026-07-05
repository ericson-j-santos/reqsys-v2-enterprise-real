# ReqSysLowCode Power Platform Solution

Entrega: 2026-07-02  
Ambiente ativo no PAC CLI durante validacao: `tieri (default)` / `https://orga258f260.crm2.dynamics.com/`

## Arquivos

| Arquivo | Uso | SHA256 |
| --- | --- | --- |
| `ReqSysLowCode_gold_unmanaged.zip` | Importar em DEV/sandbox para evolucao da solution | `3983A8C4A009FB86B1A6D890A25F3DB3E2023F713A1E6358D7B86A1F855FD7D3` |
| `ReqSysLowCode_gold_managed.zip` | Promocao controlada para ambientes superiores apos validacao | `6846E874AADE38AFB3011EA637487DB7849261577169D817C64C8B93400B241A` |

## Validacao

Gerado com Power Platform CLI:

```powershell
pac solution pack --zipfile artifacts\lowcode-solution-factory\powerplatform-standard\ReqSysLowCode_gold_unmanaged.zip --folder artifacts\lowcode-solution-factory\powerplatform-standard\src\src --packagetype Unmanaged
pac solution pack --zipfile artifacts\lowcode-solution-factory\powerplatform-standard\ReqSysLowCode_gold_managed.zip --folder artifacts\lowcode-solution-factory\powerplatform-standard\src\src --packagetype Managed
```

Checker oficial:

```powershell
pac solution check --path artifacts\lowcode-solution-factory\powerplatform-standard\ReqSysLowCode_gold_unmanaged.zip --outputDirectory artifacts\lowcode-solution-factory\powerplatform-standard\checker-gold-unmanaged --geo UnitedStates
```

Resultado:

```text
Critical: 0
High: 0
Medium: 0
Low: 0
Informational: 0
```

## Como importar em DEV

1. Acesse `https://make.powerapps.com`.
2. Selecione o ambiente DEV/sandbox.
3. Abra `Solutions`.
4. Clique em `Import solution`.
5. Selecione `ReqSysLowCode_gold_unmanaged.zip`.
6. Avance e confirme a importacao.
7. Publique customizacoes se o Power Platform solicitar.

## Observacao

Este ZIP e uma solution Power Platform valida/importavel criada pelo PAC CLI como container ALM `ReqSysLowCode`.

Ele inclui 5 web resources dentro da propria solution:

- `reqsys_/lowcode/canvas.htm`
- `reqsys_/lowcode/manifest.htm`
- `reqsys_/lowcode/dataverse-schema.htm`
- `reqsys_/lowcode/powerautomate-flows.htm`
- `reqsys_/lowcode/copilot-security-alm.htm`

Esses web resources carregam o canvas, manifesto, contrato Dataverse, flows Power Automate, Copilot Studio, security roles e plano ALM dentro do ZIP importado.

Proxima etapa: materializar esses contratos como componentes nativos da solution, isto e, tabelas Dataverse, Canvas App, flows Power Automate, agente Copilot Studio e security roles reais.
