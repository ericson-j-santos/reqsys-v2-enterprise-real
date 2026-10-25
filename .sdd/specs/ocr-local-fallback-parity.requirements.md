# OCR local fallback parity — autonomia sem drift

## Objetivo

Preservar `backend/ocr_evidencia` apenas como snapshot de contingência para
DEV/teste/offline, sem permitir que ele se torne uma implementação paralela ao
`ocr-evidence-engine` pinado.

A fonte canônica de runtime e deploy continua sendo o pacote externo
`ericson-j-santos/ocr-evidence-engine` no SHA
`15dd067032d7c55e22186ef3587c0d694d0392fd`.

## Decisão arquitetural

A remoção física imediata da cópia local fica **deferida por desenho** porque
ela reduziria a autonomia offline/local: `app.ocr.worker` importa
`ocr_evidencia` no carregamento do bounded context OCR.

Em vez de remoção, o snapshot local deve ser governado por paridade:

- código executável idêntico ao engine pinado;
- diferenças somente documentais/identidade local explicitamente permitidas;
- nenhuma lógica adicional no snapshot;
- produção e deploy continuam obrigatoriamente no wheel externo;
- qualquer divergência bloqueia o OCR Benchmark Gate.

## Requisito 1 — identidade do fornecedor

O lock deve continuar apontando para o repositório privado exato, versão
`1.2.0` e SHA completo
`15dd067032d7c55e22186ef3587c0d694d0392fd`.

## Requisito 2 — conjunto de código executável

O snapshot local e `src/ocr_evidencia` do fornecedor pinado devem ter o mesmo
conjunto de arquivos Python.

Nenhum módulo Python extra pode existir apenas no snapshot local.

## Requisito 3 — paridade byte a byte

Todos os módulos executáveis, exceto o `__init__.py` raiz, devem ser byte a
byte idênticos ao fornecedor pinado.

O `__init__.py` raiz pode diferir somente no docstring. Ele deve manter:

- `__version__ == "1.2.0"`;
- `__all__ == ["__version__"]`;
- nenhuma chamada, import adicional, definição ou efeito colateral.

## Requisito 4 — proveniência coerente

O `PROVENANCE.md` local pode explicar a função de fallback ReqSys, mas deve
conter a mesma versão, SHA-256 do gerador e SHA-256 do payload do fornecedor.

## Requisito 5 — produção externa obrigatória

Os caminhos canônicos de deploy devem continuar com
`OCR_EXTERNAL_PACKAGE_REQUIRED=1`.

No modo externo obrigatório, o Dockerfile deve:

1. instalar o wheel verificado;
2. remover `/app/ocr_evidencia`;
3. provar import a partir de `site-packages`;
4. falhar se o bundle externo estiver ausente ou inconsistente.

## Requisito 6 — controle contra falso positivo

O CI deve executar a validação de paridade contra um checkout real do fornecedor
no SHA do lock.

Um controle negativo automatizado deve adulterar uma cópia temporária de um
módulo local e provar que o validador rejeita o drift.

## Requisito 7 — contrato externo continua obrigatório

O job deve continuar provando separadamente que, sem a cópia local, o import
falha antes da instalação e passa após a instalação do wheel externo em
`site-packages`.

Paridade do fallback não substitui o External Package Contract.

## Requisito 8 — fronteira operacional

Este incremento:

- não executa deploy;
- não promove HML/STG/PROD;
- não altera o pin do engine;
- não altera o código do engine;
- não remove o fallback local;
- não autoriza uso do fallback em produção.

## Critérios de aceite

1. Validador de paridade passa no HEAD exato.
2. Conjunto de `.py` é idêntico entre snapshot e engine.
3. Módulos executáveis relevantes são byte-idênticos.
4. `__init__.py` difere apenas por docstring e mantém contrato público.
5. Proveniência compartilha versão/gerador/payload.
6. Controle negativo de drift falha como esperado.
7. OCR External Package Contract continua verde.
8. OCR External Runtime Image Contract continua verde.
9. Evidence Gate v2 continua 10/10.
10. Nenhum deploy ou produção é tocado.
11. Custo adicional da validação é R$ 0,00.

## Extensão — cobertura do gatilho OCR Benchmark Gate (24/10/2026)

Correção preventiva: mudanças nos contratos e no validador da paridade do
fallback local não podem escapar do gate por omissão do filtro de caminhos
`pull_request.paths` em `.github/workflows/ocr-benchmark.yml`.

### Critérios de aceite adicionais

12. Alterações em `scripts/validate_ocr_local_fallback_parity.py`, nos três
    testes `test_ocr_local_fallback_parity.py`,
    `test_ocr_external_package_workflow.py` e
    `test_ocr_external_runtime_package.py`, no `backend/pyproject.toml` e nas
    especificações OCR relevantes acionam o OCR Benchmark Gate.
13. `tests/test_ocr_external_package_workflow.py` verifica a cobertura dos
    caminhos críticos e comprova o controle negativo de arquivo não relacionado.
14. O gate executa os contratos de pacote instalado, imagem externa, paridade e
    Evidence Gate v2 no HEAD da PR; ausência/skipped é reprovação, não aprovação.
15. O SHA do motor e a versão 1.2.0 continuam fixados, e
    `backend/ocr_evidencia` permanece versionado e disponível apenas para
    DEV/teste/offline. Nenhum deploy, produção ou remoção é autorizada.
