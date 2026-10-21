# Post-merge Runtime Smoke Sentinel — PC24x7 DEV

## Problema
O antigo workflow `Runtime Production Smoke Governed` foi desativado após a retirada do Fly.io (`if: false`). Seu sentinel pós-merge continua disparando para uma origem permanentemente `skipped`, sem artefato; o erro de contrato não fornece prova funcional do PC24x7 atual.

## Requisitos
1. Substituir exclusivamente a **origem** da validação por `Validação de Acessos Públicos — ReqSys`, workflow GitHub existente, sem ativar Fly.io e sem criar workflows novos.
2. Verificar identidade por nome e `workflow_id`, evento `push` e branch `main`, resultado `success` e SHA completo correspondente ao SHA atual da `main`, lido por API.
3. Confirmar que o job real `Validar URLs públicas e gerar analítico` terminou em `success` e executou (não skipped) locator DEV assinado, classificação de drift, health/build-info com política de SHA por escopo, validação de URLs e publicação da evidência.
4. Exigir artefato `validacao-acessos-publicos` único, não expirado e não vazio; falhar fechado em ausência, expiração, SHA divergente, payload inválido, falta de token, consulta remota indisponível, workflow/job/etapa ignorada ou falha.
5. A prova do upstream só é considerada quando seus contratos realmente executaram; não chamar `ready` um HTTP 200 isolado ou um run `skipped`. Não aceitar `workflow_dispatch` com testes possivelmente relaxados como prova pós-merge.
6. Não publicar versão, executar deploy, reiniciar host, modificar capacidades, licenças, credenciais, billing, branch protegida ou dado de produção.
7. A divergência atual do runtime (`a85e6cd6...` vs `bcff2c18...`) permanece bloqueio legítimo; corrigir o encadeamento de evidência não significa atualizar o runtime automaticamente.

## Testes
- Positivo: origem, job, cinco etapas, artefato e SHA atual aprovados.
- Negativos: `skipped`, `failure`, job/etapa ignorado, evento incorreto, origem legada, artefato ausente/expirado/vazio, SHA da main diferente, token ausente e erro de API.
- Repetição idempotente da mesma evidência; nenhum side effect externo.
- Conferir jobs e artifact de upstream real no SHA do incremento após CI e garantir ausência de promoção indevida quando runtime estiver atrasado.

## Critério de aceite
- Check Pre-PR `READY_FOR_PR=passed` no HEAD e base correntes antes da abertura da PR.
- CI de contratos positivo/negativo efetivamente executado no SHA, sem mock promovido a E2E.
- Fonte ativa vinculada, falha fechada onde necessário e publicação de evidência sanitizada.
- E2E de runtime só será `ready` quando o job público real produzir proof completo e SHA observado for compatível com a política de implantação. Se a versão continuar defasada, estado bloqueado explícito.
- Custo incremental R$ 0 e nenhum deploy em DEV/PROD nesta PR.
