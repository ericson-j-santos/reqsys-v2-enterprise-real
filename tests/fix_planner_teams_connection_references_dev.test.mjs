import test from 'node:test'
import assert from 'node:assert/strict'

import {
  chooseConnection,
  hasExpectedNativeReferences,
  nativeConnectionReferences,
  normalizeConnectionId,
  selectTargetSolution,
  sha256Json,
} from '../scripts/fix_planner_teams_connection_references_dev.mjs'

test('normaliza connection id sem expor o caminho ARM', () => {
  assert.equal(
    normalizeConnectionId(
      '/providers/Microsoft.PowerApps/apis/shared_teams/connections/abc123',
    ),
    'abc123',
  )
  assert.equal(normalizeConnectionId('abc123'), 'abc123')
})

test('gera referencias nativas de solution e rejeita connectionName direto', () => {
  const logical = {
    planner: 'reqsys_sharedplanner_plannerteams',
    teams: 'reqsys_sharedteams_plannerteams',
  }
  const refs = nativeConnectionReferences(logical)

  assert.equal(hasExpectedNativeReferences(refs, logical), true)

  const direct = structuredClone(refs)
  direct.shared_teams.connectionName = 'connection-123'
  assert.equal(hasExpectedNativeReferences(direct, logical), false)
})

test('hash canonico nao depende da ordem das propriedades', () => {
  assert.equal(
    sha256Json({ b: 2, a: { y: 2, x: 1 } }),
    sha256Json({ a: { x: 1, y: 2 }, b: 2 }),
  )
})

test('seleciona uma unica solution custom comum e evita Default', () => {
  const solutions = [
    {
      solutionid: '11111111-1111-1111-1111-111111111111',
      uniquename: 'Default',
      friendlyname: 'Default Solution',
      ismanaged: false,
    },
    {
      solutionid: '22222222-2222-2222-2222-222222222222',
      uniquename: 'ReqSysDev',
      friendlyname: 'ReqSys Dev',
      ismanaged: false,
    },
  ]
  const ids = new Set([
    '11111111-1111-1111-1111-111111111111',
    '22222222-2222-2222-2222-222222222222',
  ])

  assert.equal(
    selectTargetSolution(solutions, ids).uniquename,
    'ReqSysDev',
  )
})

test('falha fechado quando ha mais de uma solution custom ReqSys', () => {
  const solutions = [
    {
      solutionid: '11111111-1111-1111-1111-111111111111',
      uniquename: 'ReqSysA',
      friendlyname: 'ReqSys A',
      ismanaged: false,
    },
    {
      solutionid: '22222222-2222-2222-2222-222222222222',
      uniquename: 'ReqSysB',
      friendlyname: 'ReqSys B',
      ismanaged: false,
    },
  ]
  const ids = new Set(solutions.map((item) => item.solutionid))

  assert.throws(
    () => selectTargetSolution(solutions, ids),
    /solution_custom_comum_ambigua/,
  )
})

test('escolhe somente conexao explicita saudavel do conector correto', () => {
  const items = [
    {
      name: 'planner-ok',
      properties: {
        apiId: '/providers/Microsoft.PowerApps/apis/shared_planner',
        statuses: [{ status: 'Connected' }],
      },
    },
    {
      name: 'teams-ok',
      properties: {
        apiId: '/providers/Microsoft.PowerApps/apis/shared_teams',
        statuses: [{ status: 'Connected' }],
      },
    },
  ]

  assert.equal(
    normalizeConnectionId(
      chooseConnection(items, 'shared_planner', 'planner-ok'),
    ),
    'planner-ok',
  )
  assert.throws(
    () => chooseConnection(items, 'shared_planner', 'missing'),
    /conexao_explicita_nao_encontrada/,
  )
})
