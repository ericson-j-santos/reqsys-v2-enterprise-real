# Security Strong Guardrails — Runbook Operacional

## Objetivo

Aplicar gates fortes de segurança no ReqSys antes de merge, revisão e produção.

Este controle não substitui revisão humana, SAST, DAST, secret scanning gerenciado, dependabot ou proteção de branch. Ele adiciona uma camada determinística mínima e bloqueante para riscos recorrentes de configuração.

## Execução

Workflow:

```text
.github/workflows/security-strong-guardrails.yml
```

Script:

```text
scripts/security_strong_guardrails.py
```

Eventos:

| Evento | Executa | Bloqueia |
|---|---:|---:|
| Pull request | Sim | Sim |
| Push na main | Sim | Sim |
| Workflow manual | Sim | Sim |

## Política de severidade

| Severidade | Efeito | Exemplo de decisão |
|---|---|---|
| Crítico | Falha o CI | Corrigir antes de revisão/merge |
| Alerta | Não falha o CI | Registrar débito e tratar em incremento específico |

## Gates críticos

| Gate | Motivo | Correção esperada |
|---|---|---|
| Auth desligada | Produção não pode operar sem autenticação | Remover flag insegura e validar login real |
| Login demonstrativo habilitado | Risco de bypass funcional | Isolar demo fora de produção |
| CORS wildcard | Exposição indevida de origem | Declarar origens explícitas por ambiente |
| JWT sem validação | Risco de aceite de token inválido | Validar assinatura, emissor, audiência e expiração |
| TLS sem validação | Risco de interceptação | Usar CA bundle corporativo |
| Dump de ambiente | Vazamento de configuração sensível | Remover log e mascarar valores |

## Evidências geradas

O workflow publica o artefato:

```text
security-strong-guardrails
```

Com os arquivos:

```text
security-reports/security-strong-guardrails.json
security-reports/security-strong-guardrails.md
```

## Procedimento em caso de falha

1. Abrir o artefato `security-strong-guardrails`.
2. Validar a linha e regra apontada.
3. Corrigir a configuração insegura.
4. Criar ou atualizar teste preventivo quando aplicável.
5. Atualizar ADR/runbook se a regra exigir exceção formal.
6. Reexecutar o CI.
7. Só marcar o PR como ready for review após CI verde.

## Critério para exceção

Exceção só pode ser aceita se houver:

- justificativa técnica;
- ambiente explicitamente não produtivo;
- prazo de expiração;
- responsável;
- issue de regularização;
- evidência de que não há exposição real.

Exceção permanente não é aceita para gates críticos de produção.

## Próximo endurecimento recomendado

| Incremento | Descrição | Prioridade |
|---|---|---:|
| Pin por SHA | Fixar actions críticas por SHA | Alta |
| Secret scanning gerenciado | Ativar varredura nativa/externa no repositório | Alta |
| CodeQL | Adicionar análise estática oficial | Alta |
| Dependabot security updates | Automatizar atualização de dependências vulneráveis | Média |
| OIDC mínimo | Reduzir uso de credenciais long-lived | Média |
