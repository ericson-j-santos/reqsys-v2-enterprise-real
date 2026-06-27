# REQSYS#002.P5 — Runbook de execução real e rollback operacional Fly.io

Este runbook operacionaliza a execução manual real do runtime público ReqSys em Fly.io, com validação do domínio `.fly.dev`, alias DuckDNS, evidência rastreável e rollback seguro por release anterior.

> Status: este documento **não declara produção pronta**. Ele define os critérios objetivos para declarar o runtime público como operacional após execução real em `dev`.

## 1. Escopo

### Dentro do escopo

- Checklist de execução manual do workflow **Fly.io Public Deploy**.
- Checklist de smoke real para URL Fly (`.fly.dev`) e alias DuckDNS.
- Rollback operacional para release anterior no Fly.io.
- Matriz de falhas comuns, sinais, ações e critérios de escalonamento.
- Template de artifact de incidente para anexar ao workflow ou ao PR operacional.
- Critérios objetivos para declarar o runtime público como **operacional**.

### Fora do escopo

- Publicação direta em produção sem passar por `dev`.
- Alteração de secrets, CORS ou JWT sem PR específico e validação dos gates de segurança.
- Correção funcional do produto fora dos endpoints públicos de runtime e health.

## 2. Pré-requisitos obrigatórios

| Item | Critério mínimo | Evidência esperada |
| --- | --- | --- |
| Branch base | `main` atualizada com PR #10 mergeado | SHA do commit ou link do PR |
| Permissão GitHub | Permissão para executar `workflow_dispatch` | Usuário executor registrado |
| Fly.io | App existente e acessível no ambiente alvo | `app_name` confirmado |
| DuckDNS | Hostname existente apontando para o alvo esperado | `duckdns_hostname` confirmado |
| Secrets | `FLY_API_TOKEN` configurado no repositório/ambiente | Apenas presença validada, sem expor valor |
| Ambiente | Começar por `dev` | `environment=dev` |

## 3. Checklist — execução manual do Fly.io Public Deploy

Execute este checklist antes de qualquer declaração operacional.

1. Abrir **Actions** no GitHub.
2. Selecionar o workflow **Fly.io Public Deploy**.
3. Acionar **Run workflow** na branch `main`.
4. Preencher os inputs:

| Input | Valor para primeira execução real |
| --- | --- |
| `environment` | `dev` |
| `app_name` | Nome do app Fly existente, por exemplo `reqsys-app-dev` ou equivalente real |
| `duckdns_hostname` | Hostname DuckDNS existente, sem inventar domínio |

5. Confirmar que o workflow iniciou no commit esperado da `main`.
6. Acompanhar todos os jobs até conclusão.
7. Registrar no artifact ou evidência operacional:
   - run id;
   - run URL;
   - commit SHA;
   - ambiente;
   - app Fly;
   - hostname DuckDNS;
   - horário de início e fim em UTC/BRT;
   - resultado final.

### Gate de aprovação do deploy

O deploy só pode seguir para smoke quando todos os itens abaixo forem verdadeiros:

- O workflow **Fly.io Public Deploy** terminou com `success`.
- O app Fly informado responde em HTTPS.
- O artifact de deploy foi publicado, quando o workflow disponibilizar artifact.
- Nenhum log expõe token, senha, CPF, PII, connection string ou segredo.
- Nenhum gate de produção foi violado, especialmente `ALLOW_DEMO_LOGIN`, `CORS_ORIGINS`, `JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE` e `JWT_EXP_MINUTES`.

## 4. Checklist — smoke real `.fly.dev` + DuckDNS

Após o deploy real em `dev`, executar o workflow **Fly.io Smoke Monitor**.

### Inputs obrigatórios

| Input | Valor esperado |
| --- | --- |
| `environment` | `dev` |
| `base_url` | `https://<app-fly>.fly.dev` |
| `duckdns_url` | `https://<hostname-duckdns>` |

### Endpoints mínimos a validar

| Alvo | Endpoint | Critério |
| --- | --- | --- |
| Fly | `/api/runtime/health` | HTTP 200 e payload de saúde válido |
| Fly | `/api/runtime/readiness` | HTTP 200 e pronto para tráfego |
| Fly | `/api/runtime/liveness` | HTTP 200 e processo ativo |
| Fly | `/api/runtime/contracts` | HTTP 200 e contrato público coerente |
| DuckDNS | `/api/runtime/health` | HTTP 200 e mesmo status operacional do Fly |
| DuckDNS | `/api/runtime/readiness` | HTTP 200 e pronto para tráfego |
| DuckDNS | `/api/runtime/liveness` | HTTP 200 e processo ativo |

### Evidência mínima do smoke

Registrar no artifact `flyio-smoke-monitor-validation-evidence` ou equivalente:

```json
{
  "schema_version": "1.0.0",
  "increment": "REQSYS#002.P5",
  "environment": "dev",
  "commit_sha": "<sha-main-executado>",
  "deploy_run_id": "<github-run-id-deploy>",
  "smoke_run_id": "<github-run-id-smoke>",
  "base_url": "https://<app-fly>.fly.dev",
  "duckdns_url": "https://<hostname-duckdns>",
  "started_at": "<iso-8601>",
  "finished_at": "<iso-8601>",
  "results": [
    { "target": "fly", "endpoint": "/api/runtime/health", "http_status": 200, "status": "success" },
    { "target": "duckdns", "endpoint": "/api/runtime/health", "http_status": 200, "status": "success" }
  ],
  "decision": "operational_candidate",
  "operator": "<github-user>"
}
```

## 5. Runbook de rollback por release anterior

Use rollback quando o deploy ou smoke real indicar indisponibilidade, regressão grave, violação de gate de segurança ou comportamento divergente entre Fly e DuckDNS.

### 5.1 Identificar release atual e anterior

```bash
fly releases --app <app_name>
```

Registrar:

- release atual;
- release anterior saudável;
- horário do deploy problemático;
- sintomas observados;
- run id do deploy/smoke.

### 5.2 Executar rollback

```bash
fly releases rollback <release_version_anterior> --app <app_name>
```

Após o rollback, executar novamente o smoke real com os mesmos inputs usados na falha.

### 5.3 Validar rollback

O rollback só é considerado concluído quando:

- `/api/runtime/health` retorna HTTP 200 no domínio Fly;
- `/api/runtime/readiness` retorna HTTP 200 no domínio Fly;
- `/api/runtime/liveness` retorna HTTP 200 no domínio Fly;
- o alias DuckDNS retorna os mesmos resultados ou há decisão formal de contingência usando `.fly.dev`;
- o incidente foi registrado com timeline, causa provável, ações executadas e estado final.

### 5.4 Contingência DNS

Se apenas DuckDNS falhar e `.fly.dev` permanecer saudável:

1. Declarar contingência DNS, não indisponibilidade total do runtime.
2. Manter `.fly.dev` como rota canônica temporária.
3. Validar resolução DNS e certificado TLS do alias DuckDNS.
4. Não promover para `staging` ou `prod` até resolver o alias ou documentar exceção aprovada.

## 6. Matriz de falhas comuns

| Sintoma | Possível causa | Ação imediata | Critério de resolução |
| --- | --- | --- | --- |
| Workflow não inicia | Permissão ou branch incorreta | Confirmar branch `main`, permissão e inputs | Run criado no commit correto |
| Deploy falha antes do release | `FLY_API_TOKEN`, config Fly ou build inválido | Validar segredo e logs sem expor valor | Job de deploy `success` |
| `.fly.dev` retorna 5xx | App indisponível, migração ou runtime quebrado | Coletar logs Fly e considerar rollback | Health/readiness/liveness HTTP 200 |
| DuckDNS não resolve | DNS desatualizado ou hostname incorreto | Validar hostname, TTL e apontamento | Alias resolve para destino esperado |
| DuckDNS resolve mas TLS falha | Certificado/roteamento incorreto | Validar certificado e configuração do proxy/edge | HTTPS válido sem erro de certificado |
| Fly saudável e DuckDNS falho | Falha restrita ao alias | Ativar contingência `.fly.dev` | Incidente DNS aberto e runtime Fly saudável |
| Smoke falha por timeout | Cold start, rede ou app lento | Reexecutar uma vez e comparar tempos | P95 aceitável e sem falha recorrente |
| Payload inesperado | Contrato de runtime divergente | Bloquear declaração operacional e abrir correção | Contrato compatível com monitor |
| Logs expõem segredo/PII | Falha de mascaramento | Interromper promoção e abrir incidente de segurança | Logs saneados e causa tratada |

## 7. Template de artifact de incidente

Salvar como artifact quando qualquer gate falhar. Nome sugerido: `flyio-runtime-incident-<environment>-<run-id>.json`. O template versionado está em `docs/evidencias-operacionais/templates/flyio-runtime-incident-template.json`.

```json
{
  "schema_version": "1.0.0",
  "incident_id": "REQSYS-RUNTIME-<yyyyMMdd-HHmm>-<environment>",
  "increment": "REQSYS#002.P5",
  "environment": "dev",
  "severity": "sev2",
  "status": "open",
  "opened_at": "<iso-8601>",
  "closed_at": null,
  "operator": "<github-user>",
  "commit_sha": "<sha>",
  "deploy_run_id": "<github-run-id>",
  "smoke_run_id": "<github-run-id>",
  "app_name": "<app-fly-existente>",
  "base_url": "https://<app-fly>.fly.dev",
  "duckdns_url": "https://<hostname-duckdns>",
  "symptoms": ["<sintoma-observado>"],
  "failed_gates": ["<gate-falho>"],
  "timeline": [
    { "at": "<iso-8601>", "event": "deploy_started", "evidence": "<url-ou-run-id>" },
    { "at": "<iso-8601>", "event": "smoke_failed", "evidence": "<url-ou-artifact>" }
  ],
  "rollback": {
    "required": true,
    "previous_release": "<release-version-anterior>",
    "executed_at": "<iso-8601>",
    "result": "pending"
  },
  "root_cause_hypothesis": "<hipotese-inicial>",
  "final_decision": "blocked",
  "follow_up_items": ["<acao-corretiva>"]
}
```

## 8. Critérios para declarar runtime público como operacional

Declarar **runtime público operacional em dev** somente quando todos os critérios forem atendidos:

1. **Deploy real concluído:** workflow **Fly.io Public Deploy** em `dev` finalizou com `success`.
2. **Smoke real concluído:** workflow **Fly.io Smoke Monitor** em `dev` finalizou com `success`.
3. **Dupla rota saudável:** `.fly.dev` e DuckDNS responderam aos endpoints mínimos com HTTP 200.
4. **Contrato preservado:** `/api/runtime/contracts` manteve schema e endpoints esperados.
5. **Evidência publicada:** artifact de validação contém commit SHA, run ids, URLs, timestamps e resultados por endpoint.
6. **Sem vazamento:** logs e artifacts não contêm tokens, senhas, CPF, PII, connection string ou segredo.
7. **Rollback conhecido:** release anterior saudável está identificado antes de promover para outro ambiente.
8. **Decisão registrada:** evidência operacional documenta `decision=operational` ou equivalente, com operador e horário.

## 9. Critérios de bloqueio

Não declarar operacional e não promover ambiente quando qualquer item abaixo ocorrer:

- Workflow de deploy ou smoke ausente, cancelado ou falho.
- Validação feita contra URL placeholder ou app inexistente.
- DuckDNS não validado e sem exceção formal registrada.
- Health passa, mas readiness ou liveness falha.
- Artifact de evidência ausente, expirado ou sem run id/commit SHA.
- Logs ou artifacts com segredo/PII.
- Rollback não testado ou release anterior não identificado em cenário de falha.

## 10. Registro de decisão pós-execução

Após a execução real em `dev`, anexar ao PR operacional ou release note:

```text
REQSYS#002.P5 — Decisão runtime público dev

Deploy workflow: <url>
Smoke workflow: <url>
Commit SHA: <sha>
App Fly: <app_name>
DuckDNS: <duckdns_url>
Resultado Fly: success/fail
Resultado DuckDNS: success/fail
Artifact: <nome/link>
Rollback release anterior identificado: sim/não
Decisão: operacional / bloqueado / contingência DNS
Responsável: <github-user>
Data/hora: <BRT e UTC>
```
