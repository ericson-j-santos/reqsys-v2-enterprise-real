# Analisador de Legado VBA — incremento 2

## Objetivo

Permitir que o ReqSys receba tanto módulos VBA exportados quanto contêineres Office com macro e produza análise técnica rastreável **sem iniciar Excel/Word e sem executar a macro**.

## Superfície de API

O roteador permanece anexado à API canônica de requisitos:

- `GET /api/requisitos/legado/vba/readiness`
- `POST /api/requisitos/legado/vba/analisar`

Ambos exigem identidade administrativa do ReqSys.

## Entradas suportadas

### Fonte VBA

- `.bas`
- `.cls`
- `.frm`
- `.vba`
- `.txt`

Limite padrão: 2 MiB, configurável por `VBA_ANALYZER_MAX_UPLOAD_BYTES`.

### Contêiner Office

- `.xlsm`
- `.xlsb`
- `.xlam`
- `.docm`
- `.dotm`

Limite padrão: 16 MiB, configurável por `VBA_ANALYZER_MAX_CONTAINER_BYTES`.

O ReqSys abre apenas a estrutura ZIP do formato OOXML, valida o arquivo e lê exclusivamente o `vbaProject.bin` esperado (`xl/vbaProject.bin` ou `word/vbaProject.bin`). O Office não é iniciado.

## Extração governada

Antes de processar `vbaProject.bin`, o serviço aplica:

1. limite de quantidade de itens do ZIP;
2. limite total descompactado;
3. bloqueio de membros criptografados;
4. bloqueio de caminhos com traversal (`..`);
5. limite de razão de compactação contra ZIP bomb;
6. limite específico do `vbaProject.bin`;
7. limite de módulos e de expansão total do código VBA.

A descompressão dos streams VBA é feita com `oletools==0.60.2`, de forma isolada sobre os bytes do `vbaProject.bin`. O parser não recebe o documento Office completo.

## Saídas

Para contêineres Office a resposta retorna:

- SHA-256 do documento recebido;
- SHA-256 do `vbaProject.bin`;
- estatísticas do ZIP;
- inventário de módulos;
- procedimentos, dependências e regras por módulo;
- riscos agregados com origem do módulo;
- candidatos a requisito com validação humana obrigatória;
- plano de modernização.

O código-fonte VBA extraído **não é devolvido integralmente nem persistido**.

## Segurança

Invariantes:

- `analysis_type=static_only`;
- `execution_performed=false`;
- `automatic_incorporation=false`;
- `source_persisted=false`;
- nenhuma chamada a Excel, Word, WScript ou COM é realizada pelo analisador;
- falhas internas do parser retornam somente o tipo técnico do erro, sem mensagem bruta;
- requisitos nunca são incorporados automaticamente.

## Limitações conhecidas

Este incremento interpreta o **código-fonte VBA armazenado no projeto**. Ele não executa o P-code, não tenta emular comportamento e não declara equivalência funcional da macro. Chamadas dinâmicas, código construído em tempo de execução e VBA stomping exigem uma trilha de análise especializada futura.

## Validação

Testes focados cobrem:

- `.xlsm` com `xl/vbaProject.bin`;
- `.docm` com caminho Office incorreto;
- bloqueio de path traversal;
- projeto sem macro;
- falha interna de parser sem vazamento de detalhe;
- roteamento da API para contêiner;
- limites independentes para fonte e contêiner;
- readiness do parser Office.
