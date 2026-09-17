# OCR — Validação Semântica de Identificadores Documentais v1

## Objetivo

Distinguir, no texto produzido pelo OCR, um identificador documental
estruturalmente consistente de ruído de leitura, sem publicar dado pessoal e
sem substituir a revisão humana.

O incremento fecha a lacuna declarada em `ocr-evidence-gate-v2.md`: o gate v2
certifica a camada OCR e a classificação de candidatos, mas "não cria novos
parsers de domínio para validar juridicamente CPF, RG/CIN ou CNH".

## Escopo

Coberto:

- CPF — dígito verificador módulo 11;
- CIN — verificada pelo dígito do CPF, que a Carteira de Identidade Nacional
  adota como número único (Decreto 10.977/2022);
- CNH — dígito verificador módulo 11 no padrão Denatran;
- RG — reconhecimento do campo apenas.

Fora de escopo, deliberadamente: autenticidade documental, titularidade,
consulta a base oficial e qualquer decisão automática sobre a demanda.

## Estados

| Estado | Significado |
|---|---|
| `VALIDO` | dígito verificador confere na leitura literal |
| `VALIDO_APOS_CORRECAO_OCR` | confere após normalizar confusão de OCR (`O`→`0`, `S`→`5`, …) |
| `INVALIDO` | dígito verificador não confere, ou sequência repetida |
| `VALIDACAO_INDISPONIVEL` | não há verificador nacional apurável |
| `FORMATO_INESPERADO` | quantidade de dígitos fora do campo |

`VALIDO` significa leitura estruturalmente consistente. Não significa
documento autêntico, válido ou pertencente a quem o apresentou.

## Decisões de projeto

**Detecção ancorada em rótulo.** Um número só é avaliado quando aparece logo
após um rótulo reconhecido (`CPF`, `CNH`, `REGISTRO`, `RG`, `CIN`, …) e dentro
de uma janela curta. Número solto em texto corrido não vira identificador:
sem a âncora, qualquer sequência de 11 dígitos — valor monetário, protocolo,
código de barras — geraria falso positivo.

**Correção de OCR não promove a válido.** Quando a leitura literal falha e a
normalização de confusões fecha o verificador, o estado é
`VALIDO_APOS_CORRECAO_OCR`, nunca `VALIDO`, e o número de correções aplicadas
fica registrado. A distinção preserva a diferença entre o que foi lido e o
que foi inferido.

**RG não é declarado válido.** O RG é emitido por órgão estadual e não possui
dígito verificador nacional padronizado. Afirmar validade seria fabricar
evidência, então o estado é `VALIDACAO_INDISPONIVEL` — e, portanto, não
confiável.

**Ramo ambíguo da CNH é indeterminado.** No padrão Denatran, quando o segundo
verificador ficaria negativo após o desconto, as implementações públicas
divergem. O módulo devolve `None` e o identificador recebe
`VALIDACAO_INDISPONIVEL` em vez de um veredito arbitrário.

**Revisão humana nunca é dispensada.** `requer_validacao_humana` é sempre
`True` e o construtor recusa qualquer tentativa de construir a ocorrência com
outro valor.

## Proteção de dado pessoal

- O valor lido nunca é armazenado no objeto nem serializado.
- `mascara` revela apenas os dois últimos dígitos, para conferência humana
  contra o documento físico, e existe somente na aplicação.
- `para_evidencia()` — a projeção publicável em CI — não carrega a máscara.
- O fingerprint é **HMAC-SHA256 com chave**, não SHA-256 puro: o espaço de 11
  dígitos é enumerável (10¹¹) e um hash sem chave seria reversível por força
  bruta. A chave vem de `OCR_IDENTIFIER_FINGERPRINT_KEY`; ausente, o módulo
  gera uma chave efêmera de processo e marca `fingerprint_escopo=EFEMERO`,
  caso em que o fingerprint só correlaciona ocorrências dentro da mesma
  execução.

## Integração com o OCR Evidence Gate v2

O gate passa a publicar, por caso, `identifiers`, `identifier_types`,
`identifier_states` e `trusted_identifiers` — nunca o valor lido. Três
critérios novos:

- `min_identifiers` — piso de detecções no cenário de identidade. Sem ele, um
  detector que não enxergasse nada passaria trivialmente nas proibições
  abaixo.
- `forbid_trusted_identifiers` — nos cenários de identidade e de conteúdo
  ambíguo, nenhum identificador pode ser classificado como confiável. Os
  valores do corpus são sintéticos e deliberadamente inválidos; aceitá-los
  seria falso positivo.
- `expect_no_identifiers` — página em branco e documento desconhecido não
  podem produzir identificador.

O fingerprint de idempotência do caso passa a incluir tipo, estado e página
dos identificadores, e não o fingerprint HMAC — que é efêmero por execução.

## Uso

```python
from app.ocr.identificadores_documentais import (
    detectar_identificadores_por_paginas,
    resumo_evidencia,
)

identificadores = detectar_identificadores_por_paginas(
    [(p.pagina, p.texto, p.confianca) for p in resultado.paginas]
)
evidencia = resumo_evidencia(identificadores)
```

## Validação

```bash
cd backend
pytest -q ocr_tests/test_identificadores_documentais.py

# Gate completo (exige tesseract, poppler, ImageMagick e reportlab)
python scripts/ocr_evidence_gate_v2.py --output artifacts/ocr-evidence-v2.json
```

## Limite atual

A validação é estrutural. Continuam fora deste incremento a verificação
contra base oficial, a leitura de campos MRZ/código de barras e qualquer
regra de decisão que dispense o revisor humano.
