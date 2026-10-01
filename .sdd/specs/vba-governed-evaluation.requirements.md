# Avaliação governada de versão VBA — Requisitos

## Objetivo

Permitir que um administrador avalie um módulo VBA exportado no fluxo completo de
análise estática, aplicação conservadora de controles, preservação estática e
empacotamento versionado com evidências, sem executar VBA, Office, COM ou comandos
presentes na macro.

## Requisitos

1. O endpoint de análise VBA existente deve permanecer compatível e inalterado.
2. A transformação governada deve aceitar inicialmente apenas módulo `.bas`
   exportado e rejeitar contêiner Office com erro estável.
3. A única alteração automática na fonte deve ser a aplicação idempotente de
   `Option Explicit`, além da normalização declarada para UTF-8/LF.
4. A candidata deve ser reanalisada pelo analisador existente e a emissão deve
   falhar se a projeção estática relevante divergir.
5. O pacote deve ser determinístico e permitir leitura independente de caminhos,
   checksums, manifesto, fontes normalizadas e evidências.
6. Literais de credencial detectáveis devem bloquear a emissão sem expor o valor.
7. O manifesto de Versão Mínima Controlada deve permanecer `EXPERIMENTAL`, conter
   controles não comprovados como `FAIL` e declarar `release_allowed=false`.
8. A resposta e o pacote devem declarar separadamente preservação estática e
   equivalência funcional, mantendo `functional_equivalence=NOT_PROVEN` e
   `compile_validation=NOT_RUN`.
9. Fonte e pacote podem ser devolvidos ao solicitante, mas não devem ser
   persistidos pelo servidor.
10. Correlação, usuário, horário e outros dados de execução não podem alterar os
    bytes do pacote canônico.

## Critérios de aceite

- Testes do analisador VBA legado e do novo fluxo ficam verdes.
- Duas requisições equivalentes, com correlações diferentes, produzem o mesmo ZIP
  e SHA-256.
- Um teste de leitura independente revalida todos os membros e checksums.
- Controles negativos cobrem autenticação, extensão Office, entrada binária,
  SemVer inválido, segredo, limite de pacote, corrupção e deriva estática.
- Um teste com `Auto_Open` e `Shell` comprova ausência de execução externa.
- O validador canônico aceita o manifesto `EXPERIMENTAL` sem liberar a candidata.
- O Pre-PR Readiness fica verde no SHA final e contra a `main` atual.
- A documentação mantém explícita a necessidade de validação dinâmica futura.
