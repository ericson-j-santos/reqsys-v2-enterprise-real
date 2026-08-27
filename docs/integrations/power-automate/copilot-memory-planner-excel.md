# Blueprint — Memória persistente do Copilot com Planner + Excel + ReqSys

Issue: #1359

## 1. Decisão de arquitetura

O mesmo arquivo Excel já sincronizado com o Planner pode ser reutilizado, mas a sincronização não deve escrever tudo na mesma tabela.

Responsabilidades:

- **Planner**: fonte operacional de tarefas, percentual, prazo e estado.
- **ReqSys**: fonte persistente da memória, histórico, deduplicação, conflitos e comandos governados.
- **Excel/SharePoint**: projeção tabular para consulta pelo Copilot e entrada explícita de pedidos de alteração.
- **Power Automate**: transporte entre os três pontos; não é a fonte da verdade.
- **Copilot Notebook**: consulta a planilha e usa a aba de memória como referência persistente.

Isso preserva o arquivo já existente e evita o ciclo `Planner -> Excel -> Planner -> Excel`.

## 2. Abas/tabelas no mesmo arquivo Excel

### `Tarefas` / `tbTarefas`

Tabela já sincronizada com o Planner. Manter o fluxo atual.

Chave obrigatória: `PlannerTaskId`.

### `Memoria` / `tbMemoriaCopilot`

Projeção somente leitura originada do ReqSys.

Colunas:

| Coluna | Uso |
|---|---|
| `MemoryId` | chave estável da memória |
| `PlannerTaskId` | vínculo com Planner |
| `Assunto` | assunto consolidado |
| `Contexto` | contexto persistente |
| `EstadoAtual` | estado evidenciado |
| `Decisao` | decisão vigente |
| `Pendencia` | lacuna ainda aberta |
| `ProximoPasso` | ação objetiva seguinte |
| `FonteUrl` | evidência/fonte |
| `DataFonte` | data da evidência |
| `Validade` | ativa/desatualizada/arquivada |
| `PlannerTitulo` | título atual/desejado |
| `PlannerStatus` | estado atual/desejado |
| `PlannerPercentual` | 0..100 |
| `PlannerPrazo` | prazo |
| `Versao` | versão da memória |
| `ContentHash` | deduplicação |
| `PlannerSyncStatus` | não solicitado/pendente/sincronizado/erro/conflito |
| `UltimoErro` | erro sanitizado |

### `AtualizacoesPlanner` / `tbAtualizacoesPlanner`

Inbox de comandos. Essa separação é intencional: a projeção de memória não deve disputar escrita com a pessoa/automação que solicita alteração no Planner.

Colunas mínimas:

| Coluna | Uso |
|---|---|
| `MemoryId` | vínculo com ReqSys |
| `PlannerTaskId` | tarefa alvo |
| `PlannerTitulo` | novo título, se aplicável |
| `PlannerStatus` | novo estado, se aplicável |
| `PlannerPercentual` | novo percentual, se aplicável |
| `PlannerPrazo` | novo prazo, se aplicável |
| `AtualizarPlanner` | `SIM` autoriza processamento |
| `StatusProcessamento` | pendente/aplicado/erro/conflito |
| `CorrelationId` | rastreabilidade |
| `UltimoErro` | mensagem operacional |

### `Historico` / `tbMemoriaHistorico` — opcional no P0

A fonte oficial do histórico é o ReqSys. Essa aba só é necessária se houver requisito de consulta do histórico diretamente no Excel/Copilot.

## 3. Endpoints ReqSys

Todos usam autenticação de administrador ou token de serviço com escopo:

`copilot_memory:sincronizar`

Endpoints:

- `POST /v1/hub-lowcode/copilot-memory/sync`
- `GET /v1/hub-lowcode/copilot-memory/items`
- `GET /v1/hub-lowcode/copilot-memory/export`
- `GET /v1/hub-lowcode/copilot-memory/summary`
- `GET /v1/hub-lowcode/copilot-memory/planner-commands`
- `POST /v1/hub-lowcode/copilot-memory/{memoryId}/planner-ack`
- `GET /v1/hub-lowcode/copilot-memory/{memoryId}/history`

Enviar `X-Correlation-ID` em todas as chamadas do Power Automate.

## 4. Fluxo A — Planner -> ReqSys -> Excel

Nome sugerido: `REQSYS - Memoria - Planner para Excel`

### Gatilho

Usar o fluxo atual de sincronização do Planner como origem quando possível. Acrescentar também reconciliação recorrente para capturar alterações que não possuam gatilho dedicado.

### Etapas

1. Ler tarefas do Planner.
2. Para cada tarefa, montar o estado Planner **completo**:
   - `plannerTaskId`
   - `plannerTitulo`
   - `plannerStatus`
   - `plannerPercentual`
   - `plannerPrazo`
3. Enviar lote para:

```json
{
  "items": [
    {
      "plannerTaskId": "<id>",
      "origem": "planner",
      "plannerTitulo": "<titulo>",
      "plannerStatus": "<status>",
      "plannerPercentual": 50,
      "plannerPrazo": "2026-09-10"
    }
  ]
}
```

4. Consultar `GET /copilot-memory/export`.
5. Fazer upsert em `tbMemoriaCopilot` pela chave `MemoryId`.
6. Nunca escrever em `tbAtualizacoesPlanner` nesse fluxo.

### Regra de idempotência

Se o conteúdo recebido for igual ao hash atual, o ReqSys retorna `changed=false` e não cria uma nova versão de histórico.

### Regra de conflito

Se existir uma atualização Excel -> Planner pendente e o Planner ainda devolver o estado anterior, o ReqSys ignora esse eco.

Se o Planner mudar para um terceiro estado enquanto há comando pendente, o ReqSys marca `plannerSyncStatus=conflito` e não sobrescreve a alteração local.

## 5. Fluxo B — Excel -> ReqSys -> Planner

Nome sugerido: `REQSYS - Memoria - Excel para Planner`

### Gatilho

Recorrência ou o mecanismo já utilizado pela planilha atual.

Processar somente linhas de `tbAtualizacoesPlanner` em que:

`AtualizarPlanner = SIM`

### Etapas

1. Ler linhas pendentes da tabela de comandos.
2. Para cada linha, chamar `POST /copilot-memory/sync` com:

```json
{
  "items": [
    {
      "memoryId": "<MemoryId>",
      "plannerTaskId": "<PlannerTaskId>",
      "origem": "excel",
      "plannerTitulo": "<novo titulo>",
      "plannerStatus": "<novo status>",
      "plannerPercentual": 75,
      "plannerPrazo": "2026-09-15",
      "atualizarPlanner": true
    }
  ]
}
```

3. Consultar `GET /copilot-memory/planner-commands`.
4. Para cada comando retornado, executar a ação de atualização da tarefa no Planner somente nos campos suportados pelo conector adotado no ambiente.
5. Em sucesso, chamar:

```json
{
  "sucesso": true,
  "plannerTaskId": "<PlannerTaskId>"
}
```

em `POST /copilot-memory/{memoryId}/planner-ack`.

6. Em falha, chamar o mesmo endpoint com:

```json
{
  "sucesso": false,
  "erro": "<mensagem sanitizada>"
}
```

7. Atualizar `StatusProcessamento` no Excel.
8. Somente após confirmação do ReqSys mudar `AtualizarPlanner` para `NAO`.

## 6. Fluxo de memória/pesquisa do Copilot

Quando uma pesquisa, conclusão ou decisão precisar persistir, usar `POST /copilot-memory/sync` com `origem=copilot`, `origem=pesquisa` ou `origem=reqsys`.

Exemplo:

```json
{
  "items": [
    {
      "memoryId": "ARQ-SSRS-PROXY-001",
      "origem": "pesquisa",
      "assunto": "Proxy Linux para SSRS",
      "contexto": "Pesquisa consolidada e evidenciada.",
      "estadoAtual": "Opções levantadas.",
      "decisao": "Manter memória no ReqSys e projetar no Excel.",
      "pendencia": "Validar restrições do ambiente corporativo.",
      "proximoPasso": "Executar prova controlada.",
      "fonteUrl": "<fonte>",
      "dataFonte": "2026-08-27",
      "validade": "ativa"
    }
  ]
}
```

## 7. Configuração do Copilot Notebook

Adicionar o arquivo Excel como referência do Notebook e instruir o Copilot a:

1. consultar `Memoria` antes de pesquisar novamente;
2. considerar `Decisao`, `Pendencia`, `ProximoPasso`, `DataFonte` e `Validade`;
3. não tratar `Tarefas` como memória de longo prazo;
4. diferenciar informação confirmada de hipótese;
5. indicar quando uma memória precisa ser atualizada.

## 8. Segurança

- Não armazenar token, segredo ou chave em Excel.
- Power Automate autentica no ReqSys por token de serviço dedicado.
- Escopo mínimo: `copilot_memory:sincronizar`.
- `X-Correlation-ID` obrigatório operacionalmente.
- Erros persistidos devem estar sem segredo.
- O flow deve parar em conflito; não usar política de "última gravação vence".

## 9. Evidência esperada

Após implantação em DEV:

- criar ou alterar uma tarefa no Planner;
- confirmar a memória em `GET /copilot-memory/items`;
- confirmar a linha correspondente em `tbMemoriaCopilot`;
- repetir a mesma sincronização e comprovar `changed=false` e versão inalterada;
- criar uma linha em `tbAtualizacoesPlanner` com `AtualizarPlanner=SIM`;
- comprovar comando em `/planner-commands`;
- aplicar no Planner e confirmar por `/planner-ack`;
- comprovar `plannerSyncStatus=sincronizado`;
- simular alteração concorrente e comprovar `plannerSyncStatus=conflito`.

## 10. Ação humana necessária no ambiente corporativo

O código ReqSys não consegue criar sozinho as conexões corporativas do Planner/Excel sem a identidade e as conexões autorizadas do tenant.

Blueprint humano:

1. Escolher o arquivo Excel existente no SharePoint/OneDrive.
2. Criar as tabelas `tbMemoriaCopilot` e `tbAtualizacoesPlanner` no mesmo arquivo.
3. Configurar conexão Planner e Excel no Power Automate com identidade autorizada.
4. Criar/configurar token de serviço ReqSys com escopo `copilot_memory:sincronizar`.
5. Implementar Flow A e Flow B conforme este documento.
6. Executar somente em DEV inicialmente.
7. Guardar URLs de execução dos dois flows como evidência.
8. Promover somente após os testes do item 9 passarem.

Critério de conclusão: Planner, ReqSys e Excel convergem para o mesmo estado sem duplicidade, sem loop e com histórico preservado.
