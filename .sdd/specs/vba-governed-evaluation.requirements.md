# Avaliação governada de VBA — Requisitos

## Objetivo

Permitir que o ReqSys avalie um módulo VBA textual no fluxo completo de análise
estática, aplicação conservadora de controles mínimos, verificação estática de
preservação e geração de pacote versionado com evidências, sem executar VBA ou
iniciar aplicativos Office.

## Requisitos

1. O analisador VBA existente deve permanecer como fonte da análise estática inicial.
2. A ferramenta deve aceitar somente módulos VBA textuais exportados no fluxo de transformação.
3. Contêineres Office devem falhar fechado nesse fluxo e continuar disponíveis apenas no analisador existente.
4. A transformação deve ser determinística e idempotente para a mesma fonte, nome e versão.
5. `Option Explicit` deve ser preservado quando existente ou adicionado após atributos do módulo.
6. Procedimentos sem handler ou labels preexistentes devem receber captura, registro e repropagação de erro.
7. Procedimentos ambíguos não devem ser reescritos automaticamente e devem deixar o gate estático incompleto.
8. Validação de entrada dependente do domínio deve ser marcada como validação dinâmica futura, sem inferência insegura.
9. O pacote ZIP deve incluir manifesto, versão semântica, SHA-256, checksums, módulo transformado, módulo de controles, instruções e rollback.
10. A comparação estática deve verificar preservação das assinaturas extraídas de procedimentos, dependências e regras de negócio.
11. O manifesto deve manter `release_allowed=false`, `execution_performed=false` e `dynamic_equivalence_proven=false`.
12. Nenhum teste deve executar Excel, Word, macro, P-code, COM ou código VBA.
13. A API deve preservar `correlation_id`, não persistir a fonte e retornar erros estruturados.
14. Versões inválidas, fonte vazia e procedimentos não encerrados devem falhar fechado.

## Critérios de aceite

- Teste HTTP exercita upload, análise, transformação, empacotamento e leitura independente do ZIP.
- Controle negativo comprova recusa de contêiner Office no fluxo de transformação.
- Repetição da mesma entrada produz o mesmo SHA-256 e os mesmos bytes de pacote.
- Suíte VBA existente permanece verde.
- Lint e compilação Python dos arquivos alterados são aprovados.
- Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato e `behind_by=0` antes da abertura da PR.
- Equivalência funcional dinâmica permanece explicitamente pendente até teste futuro em ambiente Office isolado.
