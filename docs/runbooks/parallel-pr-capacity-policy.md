# Política de Capacidade para PRs Paralelos

> Atualização: 2026-06-30 13:30 BRT  
> Escopo: governança de PRs paralelos sem alteração de runtime.

## Objetivo

Definir critérios objetivos para abrir múltiplos PRs simultâneos no ReqSys sem degradar estabilidade, mergeabilidade, rastreabilidade ou funcionamento atual da aplicação.

## Regra canônica

PRs paralelos são permitidos somente quando todos os itens abaixo forem verdadeiros:

1. A branch nasce da `main` atualizada.
2. O PR não altera arquivos já modificados por outro PR aberto.
3. O escopo é pequeno, reversível e com baixo acoplamento.
4. O incremento preserva contratos públicos de API, payloads, rotas, autenticação, CI/CD e deploy.
5. O PR possui rollback documentado.
6. O CI deve ficar verde antes de ser considerado pronto para merge.

## Limites recomendados

| Tipo de incremento | Paralelismo recomendado | Risco | Observação |
| --- | ---: | --- | --- |
| Documentação isolada | 3 a 5 PRs | Baixo | Preferir arquivos novos e caminhos próprios. |
| Dados estáticos versionados | 2 a 4 PRs | Baixo | Evitar editar índices compartilhados no mesmo ciclo. |
| Testes unitários isolados | 2 a 3 PRs | Médio | Evitar fixtures globais compartilhadas. |
| Frontend funcional | 1 a 2 PRs | Médio/Alto | Só paralelizar por telas independentes. |
| Backend/API | 1 PR | Alto | Evitar mudanças simultâneas em contratos. |
| CI/CD e deploy | 1 PR | Alto | Não paralelizar workflows críticos. |

## Semáforo operacional

| Cor | Condição | Ação |
| --- | --- | --- |
| Verde | Arquivos isolados, CI verde, sem conflito | Habilitar auto-merge ou merge manual. |
| Amarelo | CI pendente, mas escopo isolado | Aguardar execução e não empilhar. |
| Vermelho | Conflito, CI falho, alteração em contrato ou deploy | Bloquear merge e abrir correção específica. |

## Checklist antes de abrir PR paralelo

- [ ] Buscar PRs abertos e verificar arquivos alterados.
- [ ] Confirmar que a branch parte de `main`.
- [ ] Evitar `CHANGELOG.md`, índices centrais e workflows quando houver múltiplos PRs ativos.
- [ ] Preferir documentação, runbooks e contratos de evidência como primeiro lote.
- [ ] Declarar impacto funcional: `nenhum` quando não há código executável.
- [ ] Declarar rollback: remover arquivos adicionados.

## Rollback

Remover os arquivos adicionados por este incremento. Não há migração, alteração de banco, deploy, workflow ou contrato runtime.

## Próximo incremento seguro

Adicionar validação automática que compare arquivos alterados entre PRs abertos e classifique risco de conflito antes de abrir novos incrementos.
