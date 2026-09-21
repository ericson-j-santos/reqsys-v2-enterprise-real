# Kindle Knowledge Local Cache — Requisitos

## Objetivo

Persistir nos hosts DEV autorizados uma cópia local, rastreável e reproduzível das sete consultas Kindle catalogadas, sem depender de Remote Desktop Commander e sem acessar produção ou segredos.

## Escopo

- Hosts autorizados: `Noteri` e `DESKTOP-PDQK954`.
- Diretório canônico: `C:\dev\chatgpt-workers\kindle-knowledge-local`.
- Execução por GitHub Actions em runners self-hosted governados.
- Fonte versionada no GitHub; o cache local é derivado e reproduzível.

## Critérios de aceite

1. O bundle gerado contém exatamente 7 consultas e todos os marcadores/tokens contratuais esperados.
2. O workflow valida o contrato em runner GitHub-hosted antes de executar qualquer job self-hosted.
3. Cada host rejeita execução quando o host observado diverge do host esperado ou quando o diretório de saída não é o caminho canônico.
4. A primeira materialização grava SQL, README e manifest; o manifest contém SHA-256 e identificadores das consultas.
5. O SQL persistido é relido de forma independente e seu SHA-256 coincide com o manifest.
6. O replay da mesma versão, executado com `--expect-no-changes`, não produz alteração adicional.
7. A evidência inclui `correlation_id`, host, quantidade de consultas, SHA-256, arquivos alterados e horário observado.
8. Nenhuma etapa lê credenciais, tokens ou segredos, e nenhuma etapa toca produção, executa deploy ou operação destrutiva.
9. O workflow permanece explicitamente allowlisted pela política de runners self-hosted.
10. A validação do SHA atual deve comprovar o contrato, os controles negativos e, quando cada runner estiver disponível, materialização + replay no host correspondente.

## Evidência esperada

A conclusão funcional exige evidência do mesmo SHA para o contrato do workflow e para os jobs executados nos hosts disponíveis. Ausência de pickup em um runner deve permanecer registrada como pendência de validação, não como sucesso implícito.
