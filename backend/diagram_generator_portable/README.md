# Diagram Generator Portable

Modulo autocontido para gerar diagramas Mermaid a partir de codigo Python.

## Uso em outro PC

```bash
python -m diagram_generator_portable --path caminho/do/projeto --type all
python -m diagram_generator_portable --show-versions
```

Saida padrao:

- `.diagrams/*.md`: diagramas Mermaid.
- `.diagrams/manifest.json`: manifesto com hash, data e tipo.
- `.diagrams/.versions/`: historico quando um diagrama existente muda.

Requisitos:

- Python 3.11 ou superior.
- Nenhuma dependencia externa.
