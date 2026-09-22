# Runbook — Verificacao real antes de declarar pronto

## Status

Obrigatorio para frentes ReqSys.

## Regra operacional

Antes de afirmar que uma correcao, PR, incremento, deploy ou gate esta pronto, verde, corrigido, apto para review ou apto para merge, validar evidencias reais no GitHub.

## Checklist minimo

1. Confirmar o PR correto.
2. Confirmar o commit head atual do PR.
3. Consultar todos os workflow runs associados ao commit head.
4. Validar status dos jobs relevantes.
5. Abrir logs dos jobs com falha.
6. Identificar job, step, causa raiz e impacto.
7. Diferenciar estado evidenciado de estado alvo.
8. Manter PR em draft se qualquer CI principal ou gate obrigatorio estiver pendente ou vermelho.
9. Nao fazer merge sem autorizacao explicita.
10. Registrar links, run ids, commit e proxima acao objetiva.

## Saida padrao

| Campo | Obrigatorio |
|---|---|
| PR | Sim |
| Branch | Sim |
| Commit head | Sim |
| Workflow | Sim |
| Status | Sim |
| Job/step com falha | Quando houver |
| Evidencia | Sim |
| Proximo passo | Sim |

## Aplicacao atual

Esta regra foi aplicada ao PR 80, relacionado ao NGINX Secure Profile. O PR deve permanecer em draft ate o CI principal e os gates obrigatorios ficarem verdes.
