import { test, expect } from '@playwright/test';

const pagina = 'docs/public-showcase/reqsys-linkedin/runtime-center/index.html';

test.describe('Runtime Operational Center P0', () => {
  test('renderiza blocos principais', async ({ page }) => {
    await page.goto(pagina);
    await expect(page.getByRole('heading', { name: 'Runtime Operational Center P0' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Health cards operacionais' })).toBeVisible();
    await expect(page.getByText('CI/CD')).toBeVisible();
    await expect(page.getByText('Deploy')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Indicadores executivos P0' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Arquitetura viva navegavel' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Centro de incidentes P0' })).toBeVisible();
  });

  test('renderiza em viewport mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(pagina);
    await expect(page.getByRole('heading', { name: 'Runtime Operational Center P0' })).toBeVisible();
    await expect(page.getByText('DEV')).toBeVisible();
    await expect(page.getByText('HOMOLOG')).toBeVisible();
    await expect(page.getByText('PROD')).toBeVisible();
  });
});
