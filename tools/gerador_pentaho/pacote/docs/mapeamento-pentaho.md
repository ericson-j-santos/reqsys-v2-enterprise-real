# Mapeamento recomendado para Pentaho Data Integration 7.1+

| Etapa observada | Nome ubíquo recomendado | Componente Pentaho | Saída obrigatória |
|---|---|---|---|
| Generate Rows | Receber demanda de treino | Data Grid / Generate Rows | demanda válida |
| monta JSON Auth | Montar solicitação de credencial | Modified Java Script Value | JSON sem log de segredo |
| SIMTR Auth | Solicitar credencial de acesso | REST Client | status + resposta |
| OK? / Auth OK? | Validar autenticação | Filter Rows | sucesso ou falha explícita |
| Query JSON / Tentativas | Definir política de tentativas | Get Variables + JavaScript | máximo e contador |
| Join | Consolidar contexto | Join Rows / Stream Lookup | demanda + autorização |
| monta JSON API | Montar solicitação de dossiê | JSON Output / JavaScript | contrato da API |
| REST API cria Dossie | Criar dossiê | REST Client | status + resposta |
| Extrair ID Dossie | Extrair identificador | JSON Input | `dossie_id` |
| tem dossie? | Classificar resultado | Filter Rows | estado final |
| gravar sucesso/falha | Persistir evidência | Text File Output / Table Output | auditoria estruturada |

## Parâmetros obrigatórios

`API_BASE_URL`, `CLIENT_ID`, `CLIENT_SECRET`, `MAX_TENTATIVAS`, `TIMEOUT_MS` e `AMBIENTE`.

## Critérios de aceite

- token e segredo ausentes do `.ktr`, histórico e logs;
- toda execução termina em um estado conhecido;
- `correlation_id` e chave de idempotência atravessam o fluxo;
- erro HTTP 4xx não é repetido automaticamente; 5xx/timeout respeita limite;
- evidência contém duração, status HTTP e identificador sintético;
- cenários de sucesso e recusa executados antes da promoção.

