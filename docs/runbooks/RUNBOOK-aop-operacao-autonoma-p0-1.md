# RUNBOOK — AOP P0.1 Operação Autônoma Governada

## Objetivo

Orientar validação e operação inicial do incremento **Autonomous Operations Platform P0.1**.

Este runbook não autoriza ações destrutivas automáticas. O objetivo é dar visibilidade, score, políticas e base de governança.

## Endpoint operacional

```http
GET /operacao-autonoma/maturidade
X-Correlation-Id: <correlation-id-opcional>
```

## Resposta esperada

| Campo | Uso |
|---|---|
| `resumo.score_consolidado` | Score atual evidenciado |
| `resumo.score_alvo` | Meta enterprise |
| `resumo.gap_consolidado` | Distância até o alvo |
| `resumo.risco_operacional` | Severidade consolidada |
| `indicadores[]` | Maturidade por pilar |
| `politicas[]` | Políticas permitidas ou bloqueadas |
| `acoes_autonomas[]` | Ações possíveis, recomendadas ou bloqueadas |
| `decisoes_governanca[]` | Regras que impedem falso avanço |

## Validação local

```bash
cd backend
python -m pytest tests/test_monitoramento_operacional.py tests/test_operacao_autonoma.py -v
```

## Validação de contrato

| Critério | Esperado |
|---|---|
| Endpoint responde 200 | Sim |
| `success=true` | Sim |
| `correlation_id` propagado | Sim |
| Score menor que alvo | Sim |
| `seguranca_consolidada=false` enquanto não houver evidência completa | Sim |
| Ação destrutiva sem health validator | Bloqueada |

## Matriz operacional

| Situação | Decisão |
|---|---|
| Falha transitória de CI | Pode ser marcada como apta para retry governado |
| Configuração insegura de produção | Bloquear deploy e registrar auditoria |
| Health degradado sem validador por componente | Não executar restart automático |
| Score abaixo de 95 | Manter gap aberto |
| Pedido de alterar status para avançado | Negar até haver evidência |

## Indicadores atuais evidenciados

| Pilar | Estado evidenciado |
|---|---:|
| Operação Autônoma | 43% |
| Observabilidade | 54% |
| Segurança Enterprise | 61% |
| CI/CD Governado | 66% |
| Governança | 72% |
| Runtime Intelligence | 40% |

## Próximo incremento

**AOP P0.2 — Runtime Health Validator + Executor Governado de Remediação**.

### Entregas mínimas

| Entrega | Objetivo |
|---|---|
| Health validator por componente | Permitir decisão operacional segura |
| Registro persistente de incidentes | Auditoria |
| Executor governado | Auto-remediação não destrutiva inicial |
| Métricas reais por execução | Score menos estático |
| Dashboard de maturidade | Visibilidade em tela |
