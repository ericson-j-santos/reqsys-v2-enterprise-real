const { test, expect } = require('@playwright/test')
const { mockResponsiveApis, loginDemo } = require('./helpers/responsiveMocks')

test('Painel de projetos apresenta a experiência Pulso separada das integrações', async ({ page }) => {
  await mockResponsiveApis(page, [
    { pattern: /\/api\/v1\/requisitos$/, body: [{ id: 7, codigo: 'REQ-007', titulo: 'Portal', descricao: 'Evolução do portal', sistema: 'Portal' }] },
    { pattern: /\/api\/v1\/agile-runtime\/work-items$/, body: [{ id: 12, codigo: 'AGI-012', requisito_id: 7, repositorio: 'acme/portal-atual', branch: 'feat/pulso', status: 'em_ci', ci_status: 'running', ci_url: 'https://example.test/ci/12', ambiente_deploy: 'dev', owner_ai: 'Time Portal', atualizado_em: '2026-10-03T10:00:00Z' }] },
    { pattern: /\/api\/v1\/rastreabilidade\/matriz/, body: { linhas: [{ requisito: 'REQ-007', repositorio: 'acme/portal-atual', entrega: 'PR #42', entrega_url: 'https://example.test/pr/42', ambiente: 'dev' }], total: 1 } },
  ])
  await loginDemo(page)

  await page.goto('/painel-projetos')

  await expect(page.getByTestId('route-painel-projetos')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Visão geral' })).toBeVisible()
  await expect(page.getByText('Panorama do portfólio')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'portal-atual', exact: true })).toBeVisible()
  await expect(page.getByText('acme/portal-atual', { exact: true })).toBeVisible()
  await expect(page.getByText('Agile Execução · projeto atual')).toBeVisible()
  await expect(page.getByText('feat/pulso')).toBeVisible()
  await expect(page.getByTestId('route-painel-integracao')).toHaveCount(0)
})
