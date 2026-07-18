# Changelog — Evidência e renderização CodeQL

## Problema

O job CodeQL dependia exclusivamente do processamento assíncrono do GitHub Code Scanning. Quando a interface não renderizava o resultado, o workflow não preservava o SARIF nem apresentava diagnóstico suficiente no resumo do job.

## Correção

- atualização de `github/codeql-action` de v3 para v4;
- `build-mode: none` explícito para Python e JavaScript/TypeScript;
- upload explícito com `upload: always`;
- espera obrigatória do processamento com `wait-for-processing: true`;
- categoria estável por linguagem;
- preservação do SARIF bruto e pós-processado;
- validação de que uma análise bem-sucedida gerou evidência SARIF;
- publicação de resumo com resultado, quantidade de arquivos, identificador SARIF e link do Code Scanning;
- upload de artefato por linguagem com retenção de 30 dias;
- inclusão das evidências CodeQL no consolidado de scanners.

## Resultado esperado

A execução deixa de depender apenas da renderização visual. Mesmo em caso de atraso ou falha de UI, o SARIF, o identificador de processamento e o resumo operacional permanecem disponíveis e auditáveis.
