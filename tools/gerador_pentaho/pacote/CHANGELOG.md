# Changelog

## 2.1.0 — 2026-08-10

- corrigidos 4 bugs reais encontrados ao rodar o job pela primeira vez num Pentaho Data Integration 7.1 real: entrada de início do job (`START`, com `draw`), tipo de step `RowGenerator`, conversão `Integer` no hash SHA-256 e serialização `JSON.stringify` de valores Java no script de preparação;
- `pentaho/executar-job.bat` agora tem fallback para instalações sem `Spoon.bat`, invocando a engine Kitchen diretamente via classpath;
- adicionado `dashboard.html`, painel autocontido (sem CDN) para acompanhar as evidências de execução (`saida/evidencias.jsonl` e `saida/evidencias_pentaho.csv`).

## 2.0.0 — 2026-08-10

- job Pentaho de orquestração com encerramento governado;
- transformação de validação de configuração;
- transformação principal com CSV, JavaScript, REST, JSON, filtros e evidência;
- parâmetros sintéticos e lançadores Kitchen para Windows e Linux;
- documentação da arquitetura job → transformação;
- contratos funcionais inferidos preservando ausência de dados corporativos.

## 1.0.0 — 2026-08-10

- extração estruturada do fluxo visível;
- substituição integral de informações potencialmente sensíveis;
- API simulada e orquestrador executável;
- idempotência, correlação, timeout, retentativa e logs estruturados;
- testes de sucesso e recusa;
- mapeamento de implementação para Pentaho 7.1+.
