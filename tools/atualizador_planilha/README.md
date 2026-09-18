# Atualizador de Planilha Autocontido

Aplicação Python com CLI e frontend desktop Tkinter para transformar dados tabulares.

## Escopo suportado

- Entrada e saída: CSV, JSON e XLSX.
- Operações: `trim`, `upper`, `lower`, `set`, `replace` e `delete`.
- CSV e JSON usam apenas a biblioteca padrão.
- XLSX requer `openpyxl>=3.1,<4`.

> O componente **não transforma qualquer tipo de informação**. Ele transforma registros tabulares nos formatos e operações suportados. PDF, imagens, áudio, documentos livres, bancos e APIs exigem adaptadores específicos, contratos de schema, validação e controles de segurança.

## Execução

```bash
python tools/atualizador_planilha/atualizador_planilha.py --ui
```

CLI:

```bash
python tools/atualizador_planilha/atualizador_planilha.py \
  --source entrada.csv \
  --destination saida.json \
  --rule nome:trim \
  --rule cidade:upper
```

Gerar pacote portátil:

```bash
python tools/atualizador_planilha/atualizador_planilha.py \
  --generate-package dist/atualizador_planilha_portatil.zip
```

No outro computador, instale Python 3.10+. Para XLSX:

```bash
python -m pip install "openpyxl>=3.1,<4"
```

## Testes

```bash
python -m unittest discover -s tools/atualizador_planilha/tests -v
```
