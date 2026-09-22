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

### Diagnóstico e reparo do WSJF.xlsx

`POST /v1/hub-lowcode/wsjf/planner-excel/excel/diagnostico`

`POST /v1/hub-lowcode/wsjf/planner-excel/excel/reparar`

## Provisionamento real

A API de gerenciamento de fluxos do Power Automate (`api.flow.microsoft.com`)
não aceita credencial app-only (client_credentials) — só token delegado do
usuário. Por isso o `/deploy` cria/atualiza o fluxo **diretamente**, sem
relay via GitHub Actions/ALM/PAC CLI:

1. Frontend adquire um token delegado via MSAL (`acquireFlowManagementToken`,
   escopo `https://service.flow.microsoft.com/.default`) e envia no header
   `X-Power-Automate-Token`.
2. Backend (`despachar` em `wsjf_planner_excel_provisioning.py`) lista os
   fluxos do ambiente (`GET .../environments/{id}/flows`) procurando um com o
   `displayName` `ReqSys WSJF - Planner para Excel`.
3. Se achar, `PATCH .../environments/{id}/flows/{id_real}` para atualizar. Se
   não achar, `POST .../environments/{id}/flows` para criar — o id é gerado
   pelo servidor, não pelo ReqSys. `PUT` nesse caminho devolve 404 de
   roteamento (verbo não mapeado) e `PATCH` com um id inventado localmente
   devolve 404 de negócio (`FlowNotFound`); confirmado em DEV nessa ordem.
4. Por isso a idempotência de "Instalar fluxo" é feita buscando pelo
   `displayName` a cada execução, não por um id fixo calculado no ReqSys.

Não usa repositório ALM externo, `GITHUB_PAT` nem solution zip/import —
essas exigem PAC CLI + Dataverse Application User, um caminho diferente e
mais pesado que não foi necessário aqui.

## A planilha precisa ser aceita pelo motor Excel do Graph

O conector Excel Online (Business) não lê o `.xlsx` como um arquivo: ele fala com
o motor Excel do Microsoft Graph. Esse motor é mais estrito que o Excel de
computador e recusa o pacote inteiro quando o índice ZIP não bate com o corpo do
arquivo ou quando faltam `docProps/core.xml` e `docProps/app.xml` — o Excel local
"recupera" e abre nos dois casos, então o problema só aparece quando o fluxo
executa, com `unsupportedWorkbook` / `FileCorruptTryRepair`.

Foi exatamente o que aconteceu no DEV: o template versionado
`templates/wsjf/WSJF.xlsx.base64` estava corrompido e foi ele que o bootstrap
enviou ao SharePoint.

Por isso:

1. `templates/wsjf/WSJF.xlsx.base64` é **gerado**, nunca editado à mão:
   `python scripts/gerar_template_wsjf.py` (e `--check` no CI). As colunas de
   `tbDemandas` vivem em `backend/wsjf_workbook_package.py`.
2. `scripts/bootstrap_wsjf_m365_dev.py` valida o template com o mesmo rigor do
   Graph e, se o `WSJF.xlsx` que já está no tenant for recusado, substitui o
   arquivo no mesmo item — preservando o id que os fluxos referenciam — depois de
   guardar o anterior como `WSJF.incompativel-<UTC>.xlsx` na mesma pasta.
   Quando o pacote antigo ainda é legível, as linhas de `tbDemandas` (inclusive
   os campos locais) são preservadas; quando não é, a planilha é recriada vazia e
   a perda fica registrada na evidência.
3. O instalador WSJF do ReqSys mostra o estado da planilha escolhida, oferece
   "Regenerar WSJF.xlsx" e o `/deploy` recusa instalar sobre uma planilha
   recusada pelo Graph. Falha de rede, permissão ou 5xx não bloqueiam a
   instalação — só a recusa do próprio pacote.

Para substituir a planilha do DEV sem passar pela tela, basta reexecutar o
workflow `Bootstrap WSJF Microsoft 365 DEV` (`workflow_dispatch`); ele mesmo
redispara o aceite real ao terminar.

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
3. `/deploy` (com token delegado) cria/atualiza o flow `ReqSys WSJF - Planner para Excel` de verdade no ambiente DEV (`POST` na criação, `PATCH` nas reexecuções, ambos reais na API do Power Automate).
4. flow importado parado (`state: Stopped`); ativação posterior é explícita.
5. criar uma tarefa no Planner e confirmar uma linha no Excel.
6. preencher `Risco` e `Próxima ação` manualmente no Excel.
7. alterar a tarefa no Planner e executar novamente.
8. confirmar a mesma linha, sem duplicidade, preservando os campos locais.

## Limite operacional atual

O aceite ponta a ponta depende de IDs reais do ambiente DEV, plano, arquivo e conexões Planner/Excel já autorizadas no tenant. O ReqSys não deve inventar nem armazenar credenciais de usuário para superar essa fronteira.
