# Cofre locator — validação do output

## Objetivo
Corrigir o uso prematuro de `steps.locator.outputs.base_url` dentro do próprio step que produz o output.

## Requisitos
1. O resolver apenas produz o output.
2. Um step posterior lê `steps.locator.outputs.base_url`.
3. Somente `https://*.trycloudflare.com` permanece aceito.
4. Nenhum fallback estático é adicionado.

## Critérios de aceite
- Locator com assinatura válida avança para o step de validação.
- URL válida não é interpretada como vazia.
- URL fora do domínio permitido continua falhando fechado.
