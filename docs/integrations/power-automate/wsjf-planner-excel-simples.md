# WSJF Planner → Excel simples

## Objetivo

Reutilizar a capacidade ALM do ReqSys para o MVP WSJF sem alterar a solução WSJF atualmente em uso e sem reutilizar as três rotinas do Copilot Memory.

## Perfil

`wsjf_planner_excel_simples`

Arquitetura:

`Planner → Power Automate (1 hora) → Excel no SharePoint → Copilot`

## Fonte oficial

O Planner é a fonte oficial dos campos sincronizados. O fluxo é unidirecional e não executa escrita no Planner.

Tabela Excel obrigatória: `tbDemandas`.

Campos sincronizados:

- `TaskId`
- `Título`
- `Bucket` (BucketId no MVP)
- `Progresso`
- `Prioridade`
- `Responsáveis` (representação disponível no payload do conector)
- `Início`
- `Vencimento`
- `Sincronizado em`

Campos locais preservados nas atualizações:

- `Bloqueado`
- `Descrição do bloqueio`
- `Próxima ação`
- `Risco`
- `Observações`

`Última alteração` e `Link Planner` são criados vazios neste MVP quando o conector não fornece informação confiável. Eles não são fabricados nem sobrescritos nas atualizações.

## Endpoints

### Contrato

`GET /v1/hub-lowcode/wsjf/planner-excel/contract`

### Validação sem implantação

`POST /v1/hub-lowcode/wsjf/planner-excel/validate`

### Provisionamento

`POST /v1/hub-lowcode/wsjf/planner-excel/deploy`

A implantação exige autenticação administrativa ou token de serviço com escopo `wsjf_powerautomate:provisionar`.

## ALM

Executor dedicado no repositório `reqsys-powerplatform-alm`:

`.github/workflows/wsjf-planner-excel-provisioning.yml`

A solution é isolada:

`WsjfPlannerExcelInstaller`

Ela não modifica `CopilotMemoryInstaller`, `ReqSysAutomacao` ou a solução WSJF atualmente em uso.

## Segurança

- somente DEV neste incremento;
- exatamente um fluxo;
- somente conectores Planner e Excel Online (Business);
- nenhuma credencial no bundle;
- conexões autorizadas são referenciadas por ID;
- fluxo importado parado por padrão;
- ativação posterior é explícita;
- nenhuma operação `UpdateTask` é permitida.

## Critério de aceite DEV

1. `/validate` retorna exatamente um fluxo e `tbDemandas`.
2. workflow ALM empacota `WsjfPlannerExcelInstaller.zip`.
3. importação encontra exatamente o flow `ReqSys WSJF - Planner para Excel` no Dataverse.
4. conectar Planner e Excel autorizados.
5. ativar somente em DEV.
6. criar uma tarefa no Planner e confirmar uma linha no Excel.
7. preencher `Risco` e `Próxima ação` manualmente no Excel.
8. alterar a tarefa no Planner e executar novamente.
9. confirmar a mesma linha, sem duplicidade, preservando os campos locais.

## Limite operacional atual

O aceite ponta a ponta depende de IDs reais do ambiente DEV, plano, arquivo e conexões Planner/Excel já autorizadas no tenant. O ReqSys não deve inventar nem armazenar credenciais de usuário para superar essa fronteira.
