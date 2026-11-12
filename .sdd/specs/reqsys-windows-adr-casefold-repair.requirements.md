# Correção da colisão de pastas ADR no Windows — ReqSys / #3138

## Problema comprovado

A árvore `main@bf1f637eb945e70b27d1b4ea298105ee925aad77` contém `docs/ADR` e `docs/adr`, caminhos distintos em Linux que conflitam em um checkout Windows comum. A issue #3138, comentário #6832066702, registra `SESSION_LAUNCH_BLOCKED` no Noteri em 12/11/2026; a leitura original do `git status` da sessão continua desconhecida. Não declarar que esta colisão seja a única causa do bloqueio.

## Objetivo

Remover a colisão de nomes na árvore versionada, preservando integralmente os arquivos e sem mudar a configuração do Windows, o Gateway, runners, segredos, permissões ou o runtime nativo.

## Requisitos de implementação

1. Mover `docs/ADR/ADR-0001-padrao-ouro-enterprise.md` para `docs/adr/ADR-0001-padrao-ouro-enterprise.md`, preservando o blob Git original `f92dc618612654891128253e65eec3c79c6db8cc`.
2. Mover `docs/ADR/INDEX.md` para `docs/adr/INDEX.md`, preservando o blob Git original `0b973a7361059e2ad2fc7d1ef3602d08e3b63833`.
3. Atualizar a referência obrigatória em `.github/workflows/governanca-padrao-ouro.yml` e a referência no inventário `docs/architecture/trilha-e/inventory.json`.
4. Rejeitar colisões entre prefixos de caminho que diferem apenas em maiúsculas/minúsculas em toda a árvore Git, não só nomes finais de arquivos.
5. Manter execução do teste preventivo pela governança em push e pull request; não permitir que um resultado verde de CI seja tratado como prova de `SESSION_LAUNCH_OK` no Noteri.
6. Preservar a PR #3141 como rascunho e bloqueada até autenticação da evidência física independente e continuidade entre hosts; este reparo é separado.
7. Exigir `READY_FOR_PR` no SHA exato, base atual, Validator independente e confirmação de custo incremental R$ 0,00 antes de PR. Merge, deploy, reparo administrativo, novos segredos e testes físicos continuam sujeitos a autorização e prova próprias.

## Critérios de aceite (Acceptance Criteria)

1. Comparação Git entre base e HEAD identifica exatamente duas renomeações, sem alteração do conteúdo de ambos os documentos.
2. `tests/test_reqsys_windows_casefold_tree.py` executado no SHA atual verifica ausência de colisões de caixa em todos os prefixos da árvore e presença dos documentos renomeados.
3. Dois controles negativos detectam conflito de caixa no diretório e conflito de caixa em arquivo; controle positivo admite árvore normalizada.
4. A verificação de documentos obrigatórios da Governança Padrão Ouro consulta `docs/adr/ADR-0001-padrao-ouro-enterprise.md`, e o inventário aponta para o mesmo caminho.
5. O SDD Gate registra o contrato no HEAD; Pre-PR Readiness exige `status=ready`, `sdd:contract=passed` e `READY_FOR_PR=passed` no mesmo SHA. Falhas ou ausência de evidência impedem abertura da PR.
6. Após integração autorizada, o Noteri deverá repetir somente a sessão governada no novo SHA e obter `SESSION_LAUNCH_OK`, `state_validated=true`, worktree limpo e readback independente. Até então, a recuperação física permanece bloqueada.

## Escopo e limites

**Ambiente de código:** GitHub/CI na branch isolada `fix/reqsys-windows-adr-casefold-3138`. **Ambiente físico:** Noteri DEV, sem execução nesta etapa.

**Origem:** reparo assistido no chat, sem alegar Builder externo, modelo/digest extra, disponibilidade de host ou aprovação de gates ainda não observada. **Rastreabilidade:** issue #3138, incidente Windows do comentário #6832066702, commit de primeiro reparo `d6863d2d2bddc608d041435767c4fb861f6448fe`, regras canônicas `chatgpt-operational-rules/main@58dcd4200f412a866278027ba9e433439a03f3b3`.

## Reversão

Antes de merge, descartar a branch isolada mediante autorização explícita; após merge, reverter somente o commit específico por PR governada, preservando os blobs originais e a rastreabilidade. Nunca aplicar `git clean`, `git reset`, `core.ignorecase` ou mutações no host como atalho.
