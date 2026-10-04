const { test, expect } = require('@playwright/test')
const {
  mockResponsiveApis,
  loginDemo,
  hasMainHorizontalOverflow,
} = require('./helpers/responsiveMocks')

function envelope(data) {
  return { success: true, data, errors: [], meta: { correlation_id: 'corr-e2e-wsjf' } }
}

async function mockWsjfInstaller(page) {
  await page.route('**/api/v1/hub-lowcode/**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    const method = route.request().method()
    let data = {}

    if (path.endsWith('/copilot-memory/install/status')) {
      data = {
        microsoft_configurado: true,
        alm_configurado: true,
        ambientes: [
          {
            id: 'environment-dev-001',
            nome: 'ReqSys desenvolvimento',
            url: 'https://reqsys-dev.crm.dynamics.com',
            tipo: 'Sandbox',
          },
        ],
      }
    } else if (path.endsWith('/copilot-memory/install/groups')) {
      data = {
        grupos: [
          { id: 'group-wsjf-001', nome: 'Equipe WSJF', email: 'equipe-wsjf@example.invalid' },
        ],
      }
    } else if (path.endsWith('/copilot-memory/install/plans')) {
      data = { planos: [{ id: 'plan-wsjf-001', titulo: 'Backlog WSJF' }] }
    } else if (path.endsWith('/copilot-memory/install/files')) {
      data = {
        arquivos: [
          {
            id: 'file-wsjf-001',
            nome: 'WSJF.xlsx',
            web_url: 'https://example.invalid/WSJF.xlsx',
            drive_id: 'drive-wsjf-001',
            excel_source: 'groups/group-wsjf-001',
          },
          {
            id: 'file-outro-001',
            nome: 'OutraPlanilha.xlsx',
            drive_id: 'drive-wsjf-001',
            excel_source: 'groups/group-wsjf-001',
          },
        ],
      }
    } else if (path.endsWith('/copilot-memory/install/connections')) {
      data = {
        planner: [{ id: 'planner-connection-001', nome: 'Planner corporativo' }],
        excel: [{ id: 'excel-connection-001', nome: 'Excel corporativo' }],
      }
    } else if (path.endsWith('/wsjf/planner-excel/contract')) {
      data = {
        profile: 'wsjf_planner_excel_simples',
        excel_table: 'tbDemandas',
        local_fields_preserved: ['Bloqueado', 'Próxima ação', 'Risco', 'Observações'],
      }
    } else if (path.endsWith('/wsjf/planner-excel/validate') && method === 'POST') {
      data = {
        profile: 'wsjf_planner_excel_simples',
        excel: { table: 'tbDemandas' },
        flows: [{ display_name: 'ReqSys WSJF - Planner para Excel' }],
      }
    } else if (path.endsWith('/wsjf/planner-excel/deploy') && method === 'POST') {
      data = {
        dispatched: true,
        correlation_id: 'corr-e2e-wsjf',
        workflow_url: 'https://example.invalid/actions/wsjf',
      }
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(envelope(data)),
    })
  })
}

test.describe('instalador Planner para Excel WSJF', () => {
  test.beforeEach(async ({ page }) => {
    await mockResponsiveApis(page)
    await mockWsjfInstaller(page)
  })

  test('descobre recursos, valida e solicita a instalação sem identificadores manuais', async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 900 })
    await loginDemo(page)

    await page.goto('/hub-lowcode/wsjf/planner-excel/instalar')

    await expect(page.getByTestId('route-wsjf-planner-excel-installer')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Instalar Planner → Excel WSJF' })).toBeVisible()
    await expect(page.getByText('Pronto para validar')).toBeVisible()
    await expect(page.getByText('WSJF.xlsx', { exact: true }).first()).toBeVisible()
    expect(await hasMainHorizontalOverflow(page)).toBe(false)

    await page.getByRole('button', { name: 'Validar', exact: true }).click()
    await expect(page.getByText(/Validação aprovada/)).toBeVisible()

    await page.getByLabel('Confirmo a instalação deste fluxo somente no ambiente de desenvolvimento').check()
    await page.getByRole('button', { name: 'Instalar fluxo' }).click()

    await expect(page.getByText(/Instalação solicitada/)).toBeVisible()
    await expect(page.getByText(/corr-e2e-wsjf/)).toBeVisible()
  })
})
