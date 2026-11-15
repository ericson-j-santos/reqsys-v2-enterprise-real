import { describe, expect, it } from 'vitest'
import { analisarLacunasCatalogo } from '../../data/diagnosticoIntegracoes.mjs'

const sha = 'a'.repeat(40)
const ativo = () => ({ id: 'REQ-APP', nome: 'ReqSys', repositorio: 'org/repo', gitShaFonte: sha, responsavel: 'ReqSys', e2eComprovado: false })

describe('Diagnóstico anti-lacunas do catálogo (snapshot não autenticado)', () => {
  it('não eleva dado documental a operação comprovada', () => {
    const resultado = analisarLacunasCatalogo([{ ...ativo(), e2eComprovado: true, readbackRecibo: 'informado', ciRecibo: 'informado' }])
    expect(resultado.registros[0].conclusaoOperacionalAutorizada).toBe(false)
    expect(resultado.progressoOperacional).toBe('NAO_MENSURAVEL_SEM_PROVAS_INDEPENDENTES')
  })
  it('marca links TODO, Redmine e GitHub não verificados sem presumir inexistência', () => {
    const codigos = analisarLacunasCatalogo([ativo()]).registros[0].avisos.map(a => a.codigo)
    expect(codigos).toContain('TODO_NAO_VINCULADO')
    expect(codigos).toContain('REDMINE_NAO_VINCULADO')
    expect(codigos).toContain('GITHUB_DEMANDA_NAO_VINCULADA')
  })
  it('identifica IDs locais duplicados sem excluir registros', () => {
    const resultado = analisarLacunasCatalogo([ativo(), ativo()])
    expect(resultado.registros).toHaveLength(2)
    expect(resultado.registros.every(a => a.avisos.some(g => g.codigo === 'ID_REPETIDO_NO_SNAPSHOT'))).toBe(true)
  })
  it('repetição idempotente não altera o catálogo de origem', () => {
    const entrada = [ativo()]
    const copia = JSON.stringify(entrada)
    expect(analisarLacunasCatalogo(entrada)).toEqual(analisarLacunasCatalogo(entrada))
    expect(JSON.stringify(entrada)).toBe(copia)
  })
  it('proíbe valor de progresso não comprovado', () => {
    expect(analisarLacunasCatalogo([ativo()]).registros[0].conclusaoOperacionalAutorizada).toBe(false)
  })
  it('detecta SHA divergente e estado concluído sem recibo como bloqueios locais', () => {
    const resultado = analisarLacunasCatalogo([{ ...ativo(), shaEsperado: 'b'.repeat(40), todoEstado: 'CONCLUÍDO' }])
    expect(resultado.registros[0].primeiroImpedimento.codigo).toBe('SHA_DIVERGENTE_NO_SNAPSHOT')
    expect(resultado.registros[0].avisos.map(a => a.codigo)).toContain('TODO_CONCLUIDO_SEM_PROVA')
    expect(resultado.registros[0].conclusaoOperacionalAutorizada).toBe(false)
  })
  it('identifica todas as origens não vinculadas e mantém a análise idempotente', () => {
    for (const repositorio of ['NAO_VINCULADO_A_REPOSITORIO', 'NAO_VINCULADO_A_VERSAO_PUBLICADA']) {
      const entrada = [{ ...ativo(), repositorio }]
      const antes = JSON.stringify(entrada)
      const primeira = analisarLacunasCatalogo(entrada)
      expect(primeira.registros[0].avisos.map(a => a.codigo)).toContain('ORIGEM_NAO_VINCULADA')
      expect(primeira.registros[0].conclusaoOperacionalAutorizada).toBe(false)
      expect(analisarLacunasCatalogo(entrada)).toEqual(primeira)
      expect(JSON.stringify(entrada)).toBe(antes)
    }
    expect(analisarLacunasCatalogo([ativo()]).registros[0].avisos.map(a => a.codigo)).not.toContain('ORIGEM_NAO_VINCULADA')
  })

  it('nega carga inválida', () => {
    expect(() => analisarLacunasCatalogo(null)).toThrow(TypeError)
  })
})
