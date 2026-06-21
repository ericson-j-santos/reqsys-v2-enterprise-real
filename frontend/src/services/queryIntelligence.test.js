import { describe, expect, it } from 'vitest'
import { analyzeSql, normalizeSql, splitSelectColumns } from './queryIntelligence'

describe('queryIntelligence', () => {
  it('normaliza SQL removendo comentários e espaços redundantes', () => {
    const sql = `SELECT * -- comentario
      FROM users`

    expect(normalizeSql(sql)).toBe('SELECT * FROM users')
  })

  it('extrai colunas preservando funções com vírgula interna', () => {
    const columns = splitSelectColumns(`
      SELECT
        cliente_id,
        coalesce(nome, 'N/I') AS nome,
        SUM(valor_total) AS total
      FROM vendas
    `)

    expect(columns).toEqual([
      'cliente_id',
      "coalesce(nome, 'N/I') AS nome",
      'SUM(valor_total) AS total',
    ])
  })

  it('analisa join, filtro e ordenação', () => {
    const result = analyzeSql(`
      SELECT u.id, u.name, o.total
      FROM users u
      JOIN orders o ON o.user_id = u.id
      WHERE o.total > 100
      ORDER BY o.total DESC
    `)

    expect(result.tables.map((item) => item.table)).toContain('users')
    expect(result.tables.map((item) => item.table)).toContain('orders')
    expect(result.joins).toHaveLength(1)
    expect(result.filters).toBe('o.total > 100')
    expect(result.orderBy).toBe('o.total DESC')
    expect(result.graph.nodes.length).toBeGreaterThan(0)
  })

  it('detecta SELECT estrela como risco', () => {
    const result = analyzeSql('SELECT * FROM clientes')

    expect(result.riskScore).toBeGreaterThanOrEqual(20)
    expect(result.findings.some((finding) => finding.message.includes('SELECT *'))).toBe(true)
  })

  it('detecta possível PII por nomes de colunas', () => {
    const result = analyzeSql('SELECT cpf, email, nome FROM clientes WHERE ativo = true')

    expect(result.findings.some((finding) => finding.type === 'lgpd')).toBe(true)
  })

  it('detecta comandos destrutivos como críticos sem executar SQL', () => {
    const result = analyzeSql('DELETE FROM clientes WHERE id = 1')

    expect(result.riskScore).toBeGreaterThanOrEqual(40)
    expect(result.findings.some((finding) => finding.type === 'seguranca')).toBe(true)
  })
})
