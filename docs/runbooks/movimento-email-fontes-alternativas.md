# Movimento: fontes alternativas de dados

## Estado e escopo

Permite substituir, por configuração, a origem SQL Server dos 4 datasets da Prospecção Movimento por uma API HTTPS ou por exportação JSON versionada em diretório aprovado. O padrão continua `sqlserver`; não existe fallback automático entre provedores. Este documento cobre apenas a **origem dos dados**. Para o envio via Microsoft Graph, ver [movimento-email-descoberta-sql-graph.md](movimento-email-descoberta-sql-graph.md).

A entrega de código não comprova integração corporativa: falta aprovar a fonte real e executar homologação com dados autorizados. Não houve provisionamento de infraestrutura nesta implementação.

## Origem e atualização

Configure os valores pelo mecanismo de segredos existente do ReqSys:

| Variável | Uso |
|---|---|
| `MOVIMENTO_EMAIL_SOURCE_PROVIDER` | `sqlserver` (padrão), `api` ou `file` |
| `MOVIMENTO_EMAIL_SOURCE_ID` | Identificador estável aprovado, 1–80 caracteres: letras, números, `_`, `-`, `.`; não incluir PII |
| `MOVIMENTO_EMAIL_SOURCE_MAX_AGE_SECONDS` | Idade máxima desde `generated_at`, padrão 86400 (24 horas); precisa ser positiva |
| `MOVIMENTO_EMAIL_SOURCE_API_URL` | Endpoint HTTPS fixo aprovado pela infraestrutura, sem query, fragmento ou credenciais na URL |
| `MOVIMENTO_EMAIL_SOURCE_API_TOKEN` | Token Bearer exclusivo para leitura da API |
| `MOVIMENTO_EMAIL_SOURCE_DIRECTORY` | Diretório aprovado de exportações para `file` |
| `MOVIMENTO_EMAIL_QUERY_TIMEOUT_SECONDS` | Timeout HTTP/SQL, padrão 30 segundos |

O agendador existente deve chamar `POST /v1/movimento-email/jobs/executar` depois da publicação diária do snapshot. O incremento não instala um agendador. A chamada continua exigindo admin ou token com escopo `movimento_email:job`. A data pode ser informada em `data_referencia`; por padrão o endpoint usa a data UTC atual.

- **API:** GET ao endpoint configurado, query `data_referencia=AAAA-MM-DD`, Bearer e `X-Correlation-ID`. Exige HTTP 200 e JSON UTF-8; não segue redirecionamentos. A URL é configuração administrativa, nunca vem do payload. Infra deve aprovar o destino e restringir egress; o conector não implementa allowlist de rede própria.
- **Arquivo:** ler exclusivamente `AAAA-MM-DD.json` dentro do diretório aprovado. O produtor deve gravar um temporário no mesmo volume e publicar por renomeação atômica após finalizar o arquivo. O runtime deve ter apenas leitura. Caminhos que resolvem para fora do diretório são recusados.
- **Atualização:** um snapshot novo por data operacional, antes do job. Rejeitar snapshots mais antigos que a validade configurada, sem timezone ou com horário mais de cinco minutos no futuro. Uma única leitura alimenta os quatro datasets do job; não há paginação. Arrays vazios são válidos e significam ausência de registros, não falta de dataset.
- **Limites:** 5 MiB por snapshot, 10 mil registros por dataset, 10 mil caracteres por campo textual. Exportações maiores precisam de outro contrato, sem truncamento silencioso.

## Contrato JSON v1

Exemplo sintético; ajustar `generated_at` ao instante real da exportação antes de testar:

```json
{
  "schema_version": 1,
  "source_id": "reqsys-ci",
  "data_referencia": "2026-09-07",
  "generated_at": "2026-09-07T12:00:00Z",
  "fechamento": [{"indicador": "Total", "valor": "10", "observacao": "Sintético"}],
  "pendencias_cadastro": [],
  "pendencias_historicas": [],
  "pendencias_observacao": []
}
```

Todos os campos do envelope são obrigatórios. Versão, origem e data devem coincidir com o job. Campos desconhecidos são recusados.

| Dataset | Campos obrigatórios | Campos opcionais |
|---|---|---|
| `fechamento` | `indicador`, `valor` (strings) | `observacao` (string, padrão vazio) |
| `pendencias_cadastro` | `protocolo`, `cliente`, `cpf`, `pendencia` (strings), `dias_em_aberto` (inteiro não negativo) | `responsavel` (string, padrão vazio) |
| `pendencias_historicas` | `periodo_referencia`, `pendencia` (strings), `quantidade` (inteiro não negativo), `percentual` (número finito não negativo) | nenhum |
| `pendencias_observacao` | `protocolo`, `tipo_inconsistencia`, `descricao` (strings) | `etapa` (string, padrão vazio) |

Cada enfileiramento a partir de snapshot registra `MOVIMENTO_EMAIL_FONTE_VALIDADA` na auditoria, com ID do dispatch, `correlation_id`, origem, versão, data, horário de geração e SHA-256 dos bytes lidos. O hash identifica o conteúdo; não é assinatura de autenticidade. A confiança depende de TLS/token ou das permissões do diretório. Os dados de negócio não são copiados para esse evento; o conteúdo do e-mail permanece na fila já existente, com seus controles de acesso e retenção.

## Homologação e rollback

1. Provisionar configuração em DEV e fonte aprovada (API ou diretório de exportação).
2. Publicar snapshot v1 e executar o job com data explícita. Conferir o evento `MOVIMENTO_EMAIL_FONTE_VALIDADA` e a fila `PENDING`.
3. Homologar falhas de fonte (snapshot ausente, vencido ou incompatível com o schema) antes de promover DEV → staging → produção.

Para rollback, trocar `MOVIMENTO_EMAIL_SOURCE_PROVIDER` de volta para `sqlserver` não remove mensagens já enfileiradas a partir de outra fonte.
