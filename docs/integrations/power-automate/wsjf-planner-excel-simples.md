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

## Provisionamento real

A API de gerenciamento de fluxos do Power Automate (`api.flow.microsoft.com`)
não aceita credencial app-only (client_credentials) — só token delegado do
usuário. Por isso o `/deploy` cria/atualiza o fluxo **diretamente**, sem
relay via GitHub Actions/ALM/PAC CLI:

1. Frontend adquire um token delegado via MSAL (`acquireFlowManagementToken`,
   escopo `https://service.flow.microsoft.com/.default`) e envia no header
   `X-Power-Automate-Token`.
2. Backend (`despachar` em `wsjf_planner_excel_provisioning.py`) faz
   `PUT .../environments/{id}/flows/{flow_guid}` com a definição do fluxo e
   as `connectionReferences` (Planner/Excel) já autorizadas pelo usuário.
3. `flow_guid` é determinístico (`uuid5` fixo por perfil): reexecutar
   "Instalar fluxo" atualiza o mesmo fluxo em vez de criar duplicatas.

Não usa repositório ALM externo, `GITHUB_PAT` nem solution zip/import —
essas exigem PAC CLI + Dataverse Application User, um caminho diferente e
mais pesado que não foi necessário aqui.

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
2. Conexões Planner e Excel Online (Business) autorizadas pelo usuário no Power Automate.
3. `/deploy` (com token delegado) cria/atualiza o flow `ReqSys WSJF - Planner para Excel` de verdade no ambiente DEV (`PUT` real na API do Power Automate).
4. flow importado parado (`state: Stopped`); ativação posterior é explícita.
5. criar uma tarefa no Planner e confirmar uma linha no Excel.
6. preencher `Risco` e `Próxima ação` manualmente no Excel.
7. alterar a tarefa no Planner e executar novamente.
8. confirmar a mesma linha, sem duplicidade, preservando os campos locais.

## Limite operacional atual

O aceite ponta a ponta depende de IDs reais do ambiente DEV, plano, arquivo e conexões Planner/Excel já autorizadas no tenant. O ReqSys não deve inventar nem armazenar credenciais de usuário para superar essa fronteira.
