# Detecção segura do ImageMagick no benchmark OCR

## Requisito 1 — evitar colisão com utilitário nativo do Windows
O benchmark OCR não pode tratar `C:\\Windows\\System32\\convert.exe` como ImageMagick apenas porque o executável está presente no `PATH`.

## Requisito 2 — validar assinatura do executável
O resolvedor deve consultar `magick` e `convert` e aceitar um candidato somente quando a execução de `-version` terminar com sucesso e a saída identificar explicitamente ImageMagick.

## Requisito 3 — falha explícita e determinística
Quando nenhum executável compatível estiver disponível, o benchmark deve falhar com erro explícito de ImageMagick não encontrado, sem executar um utilitário incompatível e sem mascarar a causa.

## Requisito 4 — preservar plataformas compatíveis
Em Linux, macOS ou Windows com ImageMagick corretamente instalado, `magick` ou `convert` continuam válidos quando a assinatura for confirmada.

## Requisito 5 — regressão automatizada
A suíte deve cobrir pelo menos o caso negativo do `convert.exe` nativo do Windows e o caso positivo de uma assinatura ImageMagick válida.

## Critérios de aceite
1. Um `convert.exe` cuja saída de `-version` não contenha `ImageMagick` é rejeitado.
2. Um executável cuja saída de `-version` contenha `ImageMagick` é aceito.
3. Na ausência de candidato válido, o resolvedor lança `RuntimeError` com mensagem explícita.
4. Os testes de contrato do benchmark OCR permanecem verdes.
5. A alteração não promove ambiente, não publica corpus/PII e não reduz os controles existentes do benchmark.
