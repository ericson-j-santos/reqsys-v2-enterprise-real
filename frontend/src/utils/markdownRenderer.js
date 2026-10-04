import DOMPurify from 'dompurify'

export function renderMarkdown(md) {
  if (!md) return ''

  let html = md
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/```mermaid([\s\S]*?)```/g, '<pre class="mermaid-block"><code>mermaid$1</code></pre>')
    .replace(/```([\s\S]*?)```/g, '<pre class="code-block"><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\b(REQ-\d+)\b/g, '<a href="/requisitos" class="req-link" title="Ver requisitos">$1</a>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      const cells = row.split('|').map(c => c.trim())
      const isHeader = cells.some(c => /^[-:]+$/.test(c))
      if (isHeader) return ''
      return `<tr>${cells.map(c => `<td>${c}</td>`).join('')}</tr>`
    })
    .replace(/^---+$/gm, '<hr>')
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
    .replace(/\n{2,}/g, '</p><p>')

  if (html.includes('<tr>')) {
    html = html.replace(/((<tr>.*<\/tr>\s*)+)/gs, '<table class="md-table">$1</table>')
  }
  html = html.replace(/((<li>.*<\/li>\s*)+)/gs, '<ul>$1</ul>')

  return DOMPurify.sanitize(`<p>${html}</p>`, {
    USE_PROFILES: { html: true },
  })
}
