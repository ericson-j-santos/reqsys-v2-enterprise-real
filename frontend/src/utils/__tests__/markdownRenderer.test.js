import { describe, expect, it } from 'vitest'
import { renderMarkdown } from '../markdownRenderer'

describe('renderMarkdown', () => {
  it('remove script, event handler e protocolo javascript de conteúdo não confiável', () => {
    const html = renderMarkdown(
      '<img src="x" onerror="alert(1)">\n\n[x](javascript:evil)\n\n<script>alert(1)</script>',
    )

    expect(html).not.toContain('<script')
    expect(html).not.toContain('onerror')
    expect(html).not.toMatch(/href=["']javascript:/i)
  })

  it('preserva markdown seguro depois da sanitização', () => {
    const html = renderMarkdown('# Título\n\n**forte**\n\n[site](https://example.com)')

    expect(html).toContain('<h1>Título</h1>')
    expect(html).toContain('<strong>forte</strong>')
    expect(html).toContain('href="https://example.com"')
  })
})
