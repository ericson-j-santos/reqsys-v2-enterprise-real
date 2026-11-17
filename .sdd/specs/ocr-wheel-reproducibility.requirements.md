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

## Extensão — publicação durável do bundle OCR (PR #2955)

O mesmo job `external-package-contract` do OCR Benchmark Gate deve publicar
um artefato recuperável **somente depois** de validar a reprodutibilidade real
dos dois builds e os contratos do consumidor. A publicação não substitui os
controles de integridade nem a verificação de download independente.

### Critérios de aceite adicionais

11. Existe exatamente um wheel no diretório do bundle, acompanhado por
    `MANIFEST.sha256`, `SHA256SUMS` e `provenance.json`; arquivos inesperados
    ou ausentes bloqueiam a publicação.
12. O relatório `artifacts/ocr-reproducibility-report.json` confirma
    `source_sha` igual ao lock do motor, `byte_identical=true`,
    `negative_control_detected=true` e hashes idênticos entre `build_a` e
    `build_b`.
13. O job recalcula SHA-256 para wheel e manifestos; conteúdo adulterado
    falha fechado. Os dois manifestos devem ser byte a byte equivalentes.
14. A toolchain registrada em `artifacts/ocr-build-toolchain.json` existe e
    os seis caminhos do contrato estão presentes no upload.
15. O upload usa `actions/upload-artifact` fixado por SHA, com
    `if-no-files-found: error`, nome `ocr-runtime-package-${{ github.sha }}`
    e retenção de 90 dias.
16. O teste `tests/test_ocr_external_runtime_package.py` protege a ordem
    validação -> publicação, a configuração e o conjunto fechado de caminhos.
17. Uma execução remota **no SHA corrente** deve comprovar upload efetivo e
    download independente, conferindo `source_sha`, conteúdo, hash do wheel
    e hashes dos manifestos. Workflow verde isolado não prova esse aceite.
18. O contrato SDD e o Pre-PR Readiness permanecem bloqueantes; correção
    não deve desativar gates, consumir dados privados nem promover DEV/PROD.

## Limites

O teste não demonstra baseline 92, corpus documental real, isolamento total de rede
ou reprodução do backend histórico desconhecido.

## Extensão — retenção seletiva dos relatórios técnicos OCR (17/11/2026)

### Critérios de aceite

19. No job `synthetic-smoke`, o arquivo `artifacts/ocr-benchmark.json` continua publicado pelo upload `ocr-benchmark`, com `if-no-files-found: error`, `if: always()` e `retention-days: 14`.
20. No job `evidence-v2`, o arquivo `artifacts/ocr-evidence-v2.json` continua publicado pelo upload `ocr-evidence-v2`, com `if-no-files-found: error`, `if: always()` e `retention-days: 14`.
21. O job `external-package-contract` continua publicando o pacote reproduzível completo e verificável por 90 dias, com validação de hashes, proveniência, controle negativo e readback independente exigido.
22. O teste `tests/test_ocr_external_runtime_package.py` protege os três prazos e a existência dos uploads; adulteração ou remoção de um prazo causa falha.
23. A mudança vale apenas para artefatos novos, não apaga evidência histórica, não altera produção, não utiliza corpus institucional, não concede autorização de merge ou deploy e não elimina testes.

**Validação operacional:** observar execução do workflow no SHA final, confirmar por API as datas de expiração dos relatórios e medir armazenamento real antes/depois, preservando o custo adicional máximo de R$ 0,00.

## Extensão — validação nativa isolada sem Docker (17/11/2026)

### Critérios de aceite adicionais

24. No job `external-package-contract`, reutilizar o wheel externo verificado e o código `ocr_distribution_evidence.py` já obtido na preparação por SHA fixo, sem criar novo serviço ou descarregar outro artefato.
25. O verificador deve rejeitar uma cópia do wheel adulterada antes da instalação, com falha específica `size_mismatch` ou `sha256_mismatch`; a verificação do bundle íntegro deve passar.
26. Criar um ambiente virtual Python isolado fora do checkout: antes de instalar, o pacote `ocr_evidencia` não deve estar acessível; depois de instalar com `--no-index --no-deps`, a origem deve estar dentro do `site-packages` desse ambiente e a versão e metadados devem ser `1.2.0`.
27. Preservar `external-runtime-image-contract`, seus controles negativo e positivo de imagem e o requisito do contrato original; o teste nativo é complementar e **não comprova funcionamento de imagem**.
28. `tests/test_ocr_external_runtime_package.py` deve proteger ordem, isolamento, falha negativa, versão e preservação dos demais jobs. A prova de CI nativa no SHA corrente deve ser conferida independentemente.
29. Sem Docker na execução nativa, sem novas permissões, sem dados pessoais, sem alterar deploy/produção, sem upload adicional e sem declarar `READY_FOR_MERGE` por testes estáticos.

**Nota de alcance:** a proibição operacional de Docker impede executar `external-runtime-image-contract`; até existir arquitetura nativa completa e aceite E2E independente, o gate de imagem/deploy continua bloqueado. Não marcar `skipped` como sucesso.
