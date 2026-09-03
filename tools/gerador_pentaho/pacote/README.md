# Fluxo de criação de dossiê — treino

Versão: 2.2.0
Compatibilidade: Node.js 18+; desenho aplicável ao Pentaho Data Integration 7.1+

## Objetivo

Reproduzir, com dados exclusivamente sintéticos, o comportamento observável do fluxo exibido na imagem: autenticar, criar dossiê, validar a resposta e produzir evidências operacionais.

Nenhum endpoint, segredo, identificador pessoal, nome de sistema interno ou consulta da origem foi reutilizado.

## Executar

Terminal 1:

```bash
node src/servidor-simulado.js
```

Terminal 2:

```bash
node src/executar-fluxo.js exemplos/demandas.json
```

Teste automatizado:

```bash
node --test testes/fluxo.test.js
```

## Executar como job Pentaho

1. Inicie a API simulada com `node src/servidor-simulado.js`.
2. Baixe o Pentaho Data Integration (Kitchen/Spoon) separadamente — não incluso neste pacote — e extraia-o para `pentaho/data-integration` (a pasta existe vazia como destino esperado). Depois defina `KETTLE_HOME` apontando para ela:

   Windows — PowerShell (prompt `PS C:\...>`, na pasta `pentaho/`):

   ```powershell
   $env:KETTLE_HOME = "$PWD\data-integration"
   ```

   ⚠️ Não use `set` no PowerShell: `set` ali é alias de `Set-Variable` (cria uma variável do PowerShell, não uma variável de ambiente) e `%cd%` não é expandido, então `KETTLE_HOME` fica vazio e o job falha com "defina KETTLE_HOME...".

   Windows — cmd.exe (prompt `C:\...>`, na pasta `pentaho/`):

   ```bat
   set "KETTLE_HOME=%cd%\data-integration"
   ```

   Linux/macOS (bash/sh, na pasta `pentaho/`):

   ```bash
   export KETTLE_HOME="$(pwd)/data-integration"
   ```

   A variável vale apenas para a sessão de terminal atual; repita o comando a cada novo terminal, ou defina-a de forma permanente nas variáveis de ambiente do sistema/usuário.

3. Execute `pentaho/executar-job.bat` no Windows ou `pentaho/executar-job.sh` no Linux.

O job `JB_TREINO_CRIAR_DOSSIES` chama primeiro `TR_VALIDAR_CONFIGURACAO` e depois `TR_CRIAR_DOSSIES_TREINO`. Consulte `docs/arquitetura-job-transformacao.md`.

As evidências são gravadas em `saida/evidencias.jsonl` (fluxo Node) e `saida/evidencias_pentaho.csv` (fluxo Pentaho).

## Dashboard de acompanhamento

Abra `dashboard.html` diretamente no navegador (sem servidor, sem CDN externo) e arraste os arquivos de `saida/` para visualizar o histórico de execuções por estado, fonte, status HTTP e duração.

## Variáveis de ambiente

Copie `.env.example` para o mecanismo de configuração do ambiente. O exemplo não contém segredo real.

| Variável         | Finalidade                  | Padrão de treino        |
| ---------------- | --------------------------- | ----------------------- |
| `API_BASE_URL`   | Endereço da API simulada    | `http://127.0.0.1:8080` |
| `CLIENT_ID`      | Identidade sintética        | `cliente-treinamento`   |
| `CLIENT_SECRET`  | Segredo injetado em runtime | obrigatório             |
| `MAX_TENTATIVAS` | Limite de tentativas        | `3`                     |
| `TIMEOUT_MS`     | Timeout por chamada         | `5000`                  |

## Linguagem ubíqua e estados

`Demanda` é a entrada; `CredencialDeAcesso`, a autorização temporária; `Dossiê`, o agregado criado; `EvidênciaDeProcessamento`, o resultado auditável.

Estados finais: `DOSSIÊ_CRIADO`, `AUTENTICAÇÃO_RECUSADA`, `CRIAÇÃO_RECUSADA`, `RESPOSTA_INVÁLIDA` e `FALHA_TÉCNICA`.

## Controles de padrão ouro

- segredo fora do código e mascarado nas evidências;
- `correlation_id` propagado em todas as chamadas;
- chave de idempotência SHA-256 por demanda;
- timeout e retentativa somente para falhas transitórias;
- logs JSON estruturados, sem payload sensível;
- validação de contrato antes e depois das chamadas;
- falhas tratadas explicitamente, sem caminhos “Faz Nada”;
- massa sintética com cenários de sucesso e recusa;
- teste automatizado de ponta a ponta.

## Aplicação no Pentaho 7.1

Os artefatos `.kjb` e `.ktr` estão em `pentaho/`. Credenciais reais devem ser parâmetros da transformação/job ou resolvidas por cofre; nunca armazenadas no `.ktr`, log ou repositório.
