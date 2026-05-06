# SKILL — Identidade Visual Institucional (DSC)

# Versão: 1.0 | Atualizado: abr/2026

# Base: Design System Institucional (DSC) — Fundamentos Visuais

# Adaptado para: HTML gerado em Python (Databricks), matplotlib/seaborn

## Objetivo

Garantir que todo artefato visual (gráfico, HTML, tabela, e-mail) siga os
tokens visuais do DSC: paleta, tipografia, bordas, sombras, opacidade,
logo e ícones.

## Use quando

- Definir cores, fontes ou espaçamentos em qualquer artefato visual.
- Criar ou revisar CSS para relatórios HTML.
- Verificar conformidade visual com a identidade institucional.
- Dúvida sobre qual cor, peso tipográfico ou ícone usar.

## NÃO cobre

- Como gerar gráficos matplotlib (ver `graficos-matplotlib`)
- Como estruturar HTML (ver `relatorios-html`)
- Regras semânticas de análise (ver `sunat-regras-analise`)

---

## Princípios do DSC (CRÍTICOS)

1. Usar sempre tokens DSC — nunca valores arbitrários fora da paleta.
2. Cor nunca é o único diferenciador de informação (acessibilidade WCAG).
3. Novos componentes devem ser construídos a partir dos tokens DSC.
4. Versão negativa do logo (branca) em fundos escuros; positiva em fundos claros.

---

## 1) Paleta de Cores

### Paleta Fixa — tokens Foundation

```python
# Azul institucional — cor predominante
AZUL = {
    "100": "#003A40",
    "90":  "#005CA9",   # referência principal
    "70":  "#0D5CA9",
    "50":  "#2D8AB8",
    "30":  "#6DB8A1",
    "10":  "#A0D2FC",
}

# Laranja institucional — destaques e acentos
LARANJA = {
    "90": "#F39200",    # referência principal
    "70": "#F5A623",
    "50": "#F7BE5A",
    "30": "#FAD48C",
    "10": "#FDE9BE",
}

# Turquesa — gradiente oceano institucional
TURQUESA = {
    "70": "#00B3AD",    # referência principal
    "50": "#3EC8C3",
    "30": "#85DAD7",
    "10": "#C2EDEB",
}

# Cinza — neutros
CINZA = {
    "90": "#404040",
    "70": "#6B6B6B",
    "50": "#9E9E9E",
    "30": "#D0D0D0",
    "10": "#F5F5F5",
}
```

### Paleta de Feedback

```python
FEEDBACK = {
    "success": "#2E7D32",   # verde   — positivo, sucesso
    "warning": "#F57C00",   # âmbar   — atenção, alerta
    "error":   "#C62828",   # vermelho — crítico, erro
    "info":    "#0277BD",   # azul    — informativo neutro
}
```

### Tokens Semânticos (usar nos artefatos)

```python
SEMANTIC = {
    # Identidade
    "brand_primary":   "#005CA9",   # Azul 90
    "brand_secondary": "#F39200",   # Laranja 90
    "brand_tertiary":  "#00B3AD",   # Turquesa 70

    # Superfícies
    "bg_page":         "#FFFFFF",
    "bg_section":      "#E8F1FA",   # fundo de seção
    "bg_header":       "#002F6C",   # cabeçalho escuro

    # Texto
    "text_primary":    "#333333",
    "text_secondary":  "#6B6B6B",
    "text_on_dark":    "#FFFFFF",
    "text_link":       "#005CA9",

    # Bordas
    "border_default":  "#D0D0D0",
    "border_accent":   "#F39200",

    # Semântica SUNAT — desempenho de indicadores
    "perf_good":       "#00B3AD",   # turquesa — desempenho positivo
    "perf_bad":        "#E83E62",   # goiaba   — desempenho negativo
    "perf_neutral":    "#9E9E9E",   # cinza    — estável / sem variação
}
```

### Regra semântica de desempenho (CRÍTICO)

- **Tons FRIOS = desempenho BOM**: Turquesa, Azul, Céu.
- **Tons QUENTES = desempenho RUIM**: Goiaba, Tangerina, Laranja.
- **Inversão obrigatória para indicadores de risco**:
  crescimento de inadimplência, AP, atraso, provisão = quente = ruim.
- Crescimento de Exposição, SGR, Contratação = frio = bom.

---

## 2) Acessibilidade de Cores (WCAG — CRÍTICO)

| Critério                       | Nível | Regra                                                          |
| ------------------------------ | ----- | -------------------------------------------------------------- |
| 1.4.3 — Contraste de texto     | AA    | Mínimo **4,5:1** (texto normal); **3:1** (≥ 18pt ou 14pt bold) |
| 1.4.6 — Contraste melhorado    | AAA   | Mínimo **7:1** (texto normal)                                  |
| 1.4.11 — Contraste não textual | AA    | Mínimo **3:1** (componentes e objetos gráficos)                |

**Combinações seguras (DSC homologadas):**

- Branco `#FFFFFF` sobre `brand_primary` (#005CA9) ✅
- Branco `#FFFFFF` sobre `bg_header` (#002F6C) ✅
- Escuro `#333333` sobre `bg_section` (#E8F1FA) ✅
- Escuro `#333333` sobre `bg_page` (#FFFFFF) ✅

**Nunca:**

- Texto claro sobre fundo claro.
- Cor como único diferenciador (sempre combinar com ícone, rótulo ou forma).

---

## 3) Tipografia

### Font Family

```python
FONT_FAMILY_HTML     = "'Brand Std', Arial, Helvetica Neue, sans-serif"
FONT_FAMILY_CHART    = "Brand Std"          # fallback: "Arial"
FONT_FAMILY_FALLBACK = "Arial"              # clusters sem fonte instalada
```

> ⚠️ Requer execução de `setup_fontes` antes de usar em gráficos ou HTML.
> Ver skill `setup-ambiente`.

### Escala tipográfica (base 16px / escala 1.125)

| Estilo         | Tamanho | Peso | Tag HTML    | Uso                    |
| -------------- | ------- | ---- | ----------- | ---------------------- |
| Display Large  | 57px    | 800  | `<h1>`      | Títulos publicitários  |
| Display Medium | 45px    | 800  | `<h1>`      | Títulos de destaque    |
| Display Small  | 36px    | 700  | `<h2>`      | Títulos de seção maior |
| Heading Large  | 32px    | 700  | `<h2>`      | Títulos de seção       |
| Heading Medium | 28px    | 700  | `<h3>`      | Subtítulos             |
| Heading Small  | 24px    | 600  | `<h3>`      | Rótulos de seção       |
| Text Large     | 18px    | 400  | `<p>`       | Corpo principal        |
| Text Medium    | 16px    | 400  | `<p>`       | **Corpo padrão**       |
| Text Small     | 14px    | 400  | `<p>`       | Texto auxiliar         |
| Label Large    | 14px    | 600  | `<label>`   | Rótulos, botões        |
| Label Medium   | 12px    | 500  | `<label>`   | Rótulos menores        |
| Label Small    | 11px    | 500  | `<caption>` | Legendas, captions     |

### Pesos recomendados por contexto

| Contexto                       | Peso       | Variante    |
| ------------------------------ | ---------- | ----------- |
| Cabeçalho do relatório         | 800        | ExtraBold   |
| Título de seção `<h2>`, `<h3>` | 700        | Bold        |
| Subtítulo, `<th>` de tabela    | 600        | SemiBold    |
| Corpo `<p>`, `<td>`            | 400        | Regular     |
| Rodapé, texto auxiliar         | 300        | Light       |
| Disclaimer IA                  | 300 italic | LightItalic |

---

## 4) Bordas

```python
BORDER_WIDTHS = {
    "none": "0px",
    "xs":   "1px",    # tabelas, cards — padrão
    "sm":   "2px",
    "md":   "4px",
    "lg":   "8px",
    "xl":   "12px",
}

BORDER_RADIUS = {
    "none":   "0px",
    "xs":     "4px",
    "sm":     "8px",
    "md":     "12px",
    "lg":     "16px",
    "xl":     "24px",
    "pill":   "500px",   # botões arredondados
    "circle": "50%",     # avatares, ícones circulares
}
```

- Estilo padrão: **solid**.
- Dashed: apenas para elementos com drag-and-drop.
- Usar **inner border** para não afetar dimensões.

---

## 5) Sombras (Elevação — Material Design 3)

```python
ELEVATIONS = {
    "0": "none",
    "1": "0px 1px 2px rgba(0,0,0,0.3), 0px 1px 3px 1px rgba(0,0,0,0.15)",
    "2": "0px 1px 2px rgba(0,0,0,0.3), 0px 2px 6px 2px rgba(0,0,0,0.15)",
    "3": "0px 4px 8px 3px rgba(0,0,0,0.15), 0px 1px 3px rgba(0,0,0,0.3)",
    "4": "0px 6px 10px 4px rgba(0,0,0,0.15), 0px 2px 3px rgba(0,0,0,0.3)",
    "5": "0px 8px 12px 6px rgba(0,0,0,0.15), 0px 4px 4px rgba(0,0,0,0.3)",
}
```

> Usar sombras apenas em artefatos **web/HTML**.
> Nunca aplicar sombras Material Design em gráficos matplotlib.

---

## 6) Opacidade

```python
OPACITY = {
    "8":  0.08, "16": 0.16, "24": 0.24, "32": 0.32,
    "40": 0.40, "48": 0.48, "56": 0.56, "64": 0.64,
}
```

> Usar apenas em overlays e fundos de componentes.
> Nunca aplicar para degradar legibilidade de texto.

---

## 7) Ícones

### Biblioteca oficial (adaptada para HTML Python)

Material Symbols via CDN (substitui `<mat-icon>` Angular do DSC original):

```html
<!-- No <head> do HTML -->
<link
  href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined"
  rel="stylesheet"
/>

<!-- Uso inline -->
<span class="material-symbols-outlined">arrow_upward</span>
```

### Ícones mais usados em relatórios SUNAT

| Ícone | Nome Material    | Uso                     |
| ----- | ---------------- | ----------------------- |
| ↑     | `arrow_upward`   | Variação positiva       |
| ↓     | `arrow_downward` | Variação negativa       |
| →     | `trending_flat`  | Estável                 |
| 📈    | `trending_up`    | Tendência de alta       |
| 📉    | `trending_down`  | Tendência de queda      |
| ⚠️    | `warning`        | Alerta / atenção        |
| ℹ️    | `info`           | Informação complementar |
| ✅    | `check_circle`   | OK / aprovado           |
| ❌    | `cancel`         | Crítico / erro          |

> ⚠️ CDN requer conexão com internet.
> Para ambientes offline ou PDF: substituir por Unicode ou SVG inline.

---

## 8) Logo

```python
# Fonte canônica: setup-ambiente. Manter sincronizado.
LOGO_PATH = (
    "/path/seguro/logo"
    "/logo_elemento_cor_chapado_negativo.png"
)
```

- Usar versão **negativa** (branca) em fundos escuros (header azul/marinho).
- Usar versão **positiva** (colorida) em fundos claros.
- Nunca distorcer proporções.
- Para embed em HTML: converter para base64 inline.

---

## Checklist visual

- [ ] Cores dentro da paleta DSC?
- [ ] Contraste mínimo 4,5:1 para texto?
- [ ] Cor nunca é o único diferenciador?
- [ ] Fonte Brand Std aplicada (ou fallback Arial)?
- [ ] Logo na versão correta para o fundo?
- [ ] Sombras apenas em HTML (não em matplotlib)?
- [ ] Opacidade apenas em overlays (não em texto)?
- [ ] Ícones com fallback para offline/PDF?
- [ ] Regra frio=bom / quente=ruim respeitada?
- [ ] Inversão aplicada para indicadores de risco?

## Changelog

| Versão | Data     | Descrição       |
| ------ | -------- | --------------- |
| 1.0    | abr/2026 | Versão inicial. |

## Anti‑padrões

- Cores fora da paleta DSC.
- Texto claro sobre fundo claro.
- Logo distorcido ou versão errada para o fundo.
- `<mat-icon>` em HTML Python (não funciona sem Angular).
- Sombras Material Design em gráficos matplotlib.
- Opacidade em texto corrido.
