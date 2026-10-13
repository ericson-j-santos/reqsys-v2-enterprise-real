# Hotfix — reprodutibilidade do wheel OCR 1.2.0

## Objetivo

Garantir que duas árvores limpas e independentes do motor
`ocr-evidence-engine` no SHA
`15dd067032d7c55e22186ef3587c0d694d0392fd`, construídas com a mesma
toolchain fixada, produzam wheel, `MANIFEST.sha256` e `SHA256SUMS`
byte a byte idênticos.

## Critérios de aceite

1. O SHA e a versão 1.2.0 do motor permanecem inalterados.
2. A toolchain Python/pip/setuptools/wheel/packaging é exata, validada e registrada.
3. `SOURCE_DATE_EPOCH` deriva do commit validado e `PYTHONHASHSEED=0`.
4. O build usa `--no-build-isolation`, sem resolver backend flutuante.
5. Dois checkouts limpos independentes produzem os três artefatos idênticos.
6. Adulteração de manifesto é detectada por controle negativo.
7. Divergência do wheel identifica membro ZIP divergente ou metadata do container.
8. Package Contract e Runtime Image Contract consomem o mesmo wheel canônico.
9. A importação do consumidor continua originada em `site-packages`.
10. Nenhum corpus real, credencial, deploy ou runtime físico é utilizado.

## Limites

O teste não demonstra baseline 92, corpus documental real, isolamento total de rede
ou reprodução do backend histórico desconhecido.
