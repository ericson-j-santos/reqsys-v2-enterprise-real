# Fly.io — retirada definitiva de todos os ambientes

## Decisão

Em 2026-10-02 o usuário determinou retirar Fly.io definitivamente de todas as soluções. Esta decisão substitui a autorização histórica de HML/PROD manual em `pc24x7-dev-fly-retirement.requirements.md`.

## Requisitos desta finalização

1. Bloquear jobs com operações, credenciais ou callers Fly.io em DEV/HML/STG/PROD com condição constante falsa.
2. Preservar condições anteriores de autorização sob `false && (...)` e interfaces dos workflows reutilizáveis.
3. Validar YAML e regressão; detectar reativação, herança indireta de URLs Fly via `env`/inputs do workflow e expressões que não bloqueiam realmente, como `false || true`.
4. Remover endpoints e fallbacks padrão `fly.dev`/`fly.io`; integrações que dependam deles devem exigir configuração explícita ou recusar a operação.
5. Tornar fail-closed os entrypoints locais de deploy, rollback, backup remoto, cutover e lifecycle ligados ao Fly.io.
6. Retirar do GitLab os jobs de deploy e OCR vinculados ao Fly.io, sem introduzir migração implícita para outro provedor.
7. Remover todos os manifestos `fly*.toml`, Dockerfiles e entrypoints específicos do Fly.io e impedir sua reintrodução pelo teste de regressão.
8. Sanitizar erros de configuração expostos pela API, sem retornar endpoints ou valores internos.
9. Fixar por SHA imutável as Actions de terceiros nos workflows tocados pelo incremento.
10. Exigir URL/manifesto explícito de runtime autorizado nas integrações remanescentes e rejeitar `fly.dev`/`fly.io` antes de qualquer chamada de rede.
11. Retirar links, catálogos, launchpads, manifests Teams e superfícies UI que ainda ofereçam Fly.io como destino.
12. Jobs skipped e validações locais não comprovam encerramento remoto, migração de dados, faturamento zerado ou exclusão da conta; essas afirmações exigem evidência autenticada do provedor.
13. A validação de PR do promotor de artefatos deve executar os testes locais sem depender de runs históricos sujeitos a expiração; download, validação por hash e publicação do bundle imutável permanecem obrigatórios no `workflow_dispatch`.

## Critérios de aceite

- Todos os jobs Fly.io identificados estão bloqueados; casos negativos detectam reativação.
- Jobs que herdam URLs Fly.io de `env` ou inputs definidos no workflow também ficam bloqueados e cobertos pelo teste de regressão.
- Scripts locais, lifecycle e caminhos GitLab recusam mutações Fly.io antes de qualquer chamada externa.
- Nenhum código operacional usa `fly.dev` ou `fly.io` como fallback; os 13 manifestos e quatro artefatos de build/boot Fly estão ausentes.
- Superfícies de UI, Teams, launchpad e scripts de rede recusam Fly.io antes de navegação ou I/O externo.
- YAML, pinagem imutável, testes regressivos e contratos GitLab passam no SHA da mudança.
- Builds independentes do Fly.io e contratos de autorização são preservados.
- A documentação separa a retirada no repositório do encerramento remoto, que só pode ser confirmado por inventário autenticado e prova de cobrança/conta.
- CI de admissão e revisão de evidência passam antes do merge.
- O gate de promoção passa em PR sem artefato externo e continua fail-closed no caminho manual de promoção imutável.
