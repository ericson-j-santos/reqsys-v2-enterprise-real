import { beforeEach, describe, expect, it } from 'vitest'
import { applyWcag22Guard } from '../wcag22Guard'

describe('wcag22Guard', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('nomeia progressbar de qualidade IA mesmo quando existe texto visual interno', () => {
    document.body.innerHTML = `
      <section data-testid="route-qualidade-ia">
        <div class="score-wrap">
          <div role="progressbar"><strong>88%</strong></div>
        </div>
      </section>
    `

    applyWcag22Guard(document)

    expect(document.querySelector('[role="progressbar"]').getAttribute('aria-label'))
      .toBe('Nota geral de qualidade de IA')
  })

  it('nomeia botão apenas com ícone sem sobrescrever nome existente', () => {
    document.body.innerHTML = `
      <button id="sem-nome"><span class="mdi mdi-robot-outline"></span></button>
      <button id="com-nome" aria-label="Nome explícito"><span class="mdi mdi-refresh"></span></button>
    `

    applyWcag22Guard(document)

    expect(document.querySelector('#sem-nome').getAttribute('aria-label')).toBe('Gerar recomendação com IA')
    expect(document.querySelector('#com-nome').getAttribute('aria-label')).toBe('Nome explícito')
  })

  it('torna regiões roláveis conhecidas acessíveis por teclado', () => {
    document.body.innerHTML = `
      <section data-testid="route-task-console">
        <pre class="payload-box">payload</pre>
      </section>
    `

    applyWcag22Guard(document)

    const region = document.querySelector('.payload-box')
    expect(region.getAttribute('tabindex')).toBe('0')
    expect(region.getAttribute('aria-label')).toBe('Prévia do payload enviado ao Flow')
  })
})
