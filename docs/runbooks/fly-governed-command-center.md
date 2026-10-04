# Runbook — Fly.io Governed Command Center

## Objetivo

Executar comandos operacionais do Fly.io pelo GitHub Actions com rastreabilidade, allowlist, confirmação explícita para produção e evidência auditável.

Este runbook faz parte da **Operational Runtime Governance Platform v1** e deve ser usado como trilho operacional padrão para ações em Fly.io quando a execução via CI/CD for mais segura do que execução local manual.

## Workflow

Arquivo:

```text
.github/workflows/fly-governed-command-center.yml
```

Nome no GitHub Actions:

```text
Fly.io Governed Command Center
```

Acionamento:

```text
workflow_dispatch
```

## Pré-requisitos

| Item | Obrigatório | Observação |
|---|---:|---|
| `FLY_API_TOKEN` | Sim | Secret do GitHub Actions com permissão no app Fly.io alvo. |
| Permissão para executar workflow | Sim | Operador deve ter permissão no repositório. |
| App Fly.io existente | Sim | Informar em `app_name`. |
| Confirmação de produção | Condicional | Obrigatória para comandos mutáveis em `production`. |

## Inputs

| Input | Tipo | Obrigatório | Uso |
|---|---|---:|---|
| `app_name` | string | Sim | Nome do app Fly.io. Ex.: `reqsys-api`. |
| `environment` | choice | Sim | `development`, `homologation` ou `production`. |
| `command` | choice | Sim | Comando operacional permitido. |
| `scale_count` | string | Não | Usado somente em `scale-count`. |
| `confirmacao` | string | Condicional | Para produção: `CONFIRMO_EXECUCAO_FLY`. |

## Allowlist de comandos

| Comando | Mutável | Requer confirmação em produção | Finalidade |
|---|---:|---:|---|
| `status` | Não | Não | Consultar estado do app. |
| `logs` | Não | Não | Coletar logs sem tail contínuo. |
| `deploy` | Sim | Sim | Executar deploy remoto. |
| `restart` | Sim | Sim | Reiniciar app. |
| `scale-count` | Sim | Sim | Ajustar quantidade de máquinas. |
| `secrets-list` | Não | Não | Listar nomes/metadados de secrets sem exibir valores. |

## Comandos fora do P0

Os comandos abaixo permanecem bloqueados no P0 e só devem entrar em versão futura com approval reforçado:

- `fly ssh console`
- `fly secrets set`
- `fly secrets unset`
- `fly volumes destroy`
- `fly apps destroy`
- comandos shell arbitrários
- migrações de banco sem executor governado dedicado

## Guardrails aplicados

1. O workflow só executa via `workflow_dispatch`.
2. O operador escolhe comandos em `choice`, sem campo de shell livre.
3. Há validação bash adicional da allowlist.
4. Comandos mutáveis em produção exigem confirmação textual exata:

```text
CONFIRMO_EXECUCAO_FLY
```

5. `scale-count` aceita apenas números de 0 a 5.
6. O job falha se `FLY_API_TOKEN` estiver ausente.
7. O artifact de evidência é publicado mesmo em falha.
8. Secrets não são impressos.

## Evidência operacional

Artifact gerado:

```text
fly-governed-command-report
```

Arquivos esperados:

| Arquivo | Finalidade |
|---|---|
| `request.json` | Inputs, ator, repositório, run id, commit e timestamp. |
| `validation.txt` | Resultado dos guardrails. |
| `execution.log` | Saída operacional do Fly.io. |
| `summary.md` | Resumo executivo da execução. |

## Procedimento recomendado

### 1. Diagnóstico seguro

Executar primeiro:

```text
command = status
```

Depois, se necessário:

```text
command = logs
```

### 2. Ação mutável em produção

Para `deploy`, `restart` ou `scale-count` em `production`, preencher:

```text
confirmacao = CONFIRMO_EXECUCAO_FLY
```

Sem essa confirmação, o workflow deve falhar por design.

### 3. Pós-execução

Validar:

- status do workflow;
- artifact `fly-governed-command-report`;
- logs do app;
- endpoint público afetado;
- PR/issue relacionado;
- necessidade de rollback.

## Rollback

| Cenário | Ação recomendada |
|---|---|
| Deploy com falha | Usar rollback nativo do Fly.io ou novo deploy de commit estável. |
| Restart sem recuperação | Consultar `logs`, validar secrets e escalar temporariamente se aplicável. |
| Scale incorreto | Reexecutar `scale-count` com valor correto. |
| Token inválido | Corrigir `FLY_API_TOKEN` em GitHub Secrets e reexecutar. |

## Critérios de aceite

- Workflow aparece em GitHub Actions.
- `status` executa sem confirmação adicional.
- `deploy`, `restart` e `scale-count` exigem confirmação em produção.
- Artifact é gerado em sucesso e falha.
- Não existe input para shell arbitrário.
- Runbook está versionado.

## Próximo incremento recomendado

Evoluir para **Fly.io Operational Adapter P1** com:

- persistência das execuções em backend;
- endpoint no Operational Actions Center;
- UI no Runtime Center;
- integração com correlation_id;
- aprovação manual por ambiente;
- política de rollback versionada;
- bloqueio automático quando CI estiver vermelho.
