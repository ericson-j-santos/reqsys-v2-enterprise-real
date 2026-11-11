# Contrato de emissor independente — ReqSys #3138 / PR #3141

## Requisitos

1. O Gateway do host jamais assina prova de prontidão com a própria autoridade. A emissão ocorre em domínio GitHub-hosted com chaves fora do host e testemunho externo de auditoria original, CAS e lease.
2. Três fontes explícitas: observação do Session Launcher, evento da auditoria Command Gateway e readback CAS, vinculadas em `witness` HMAC de custódia distinta da chave de emissão; API GitHub oficial para run/job/runner e labels.
3. Falhar fechado sem issuer permitido, assinatura, chave distinta, contexto hosted, SHA, host/runner, timeout, cost_zero_confirmed, gates, lease, checkpoint, audibilidade ou API GitHub.
4. `event_id` e hashes imutáveis; replay idêntico é determinístico. Saída nunca indica `dispatch_allowed`, `ready_for_work` ou `continuity_certified` como verdadeiro.
5. Não ativar executor físico, workflow, segredos, labels, Docker ou deployment por esta alteração. O operador externo **não está implantado** até registro seguro de custódia e integração física.
6. O CI de PR deve usar Chrome pré-instalado e validar versão antes dos testes reais dos workflows UX Evidence e CI E2E. Não converter falhas em sucesso/skipped, nem reduzir suíte de testes.

## Aceite incremental

- Testes positivos com witness e API GitHub simulados e controles negativos por alteração da assinatura, chave, host, SHA, runner, lease, checkpoint, origem, expiração e custo.
- CLI bloqueia antes de gravar recibo em contexto sem credenciais/sem witness; saída sanitizada e restrita.
- Pre-PR no novo SHA, CI UX/CI E2E reais e validação de código; falha não dispensa gate.
- Após implantação externa futura: readback físico do Gateway original, dois hosts distintos e replay de tarefa real, antes de certificação operacional.
