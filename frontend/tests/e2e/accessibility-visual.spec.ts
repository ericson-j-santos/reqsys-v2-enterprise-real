import fs from 'node:fs';
import path from 'node:path';
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const baseURL = process.env.E2E_BASE_URL || process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:4173';
const tagsWcagAA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

function persistirJson(nome: string, valor: unknown) {
  const diretorio = path.resolve(process.cwd(), 'test-results/accessibility');
  fs.mkdirSync(diretorio, { recursive: true });
  fs.writeFileSync(path.join(diretorio, nome), `${JSON.stringify(valor, null, 2)}\n`, 'utf8');
}

for (const viewport of [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
]) {
  test.describe(`qualidade visual ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test('não possui violações WCAG 2.2 A/AA nem overflow horizontal', async ({ page }, testInfo) => {
      await page.goto(baseURL, { waitUntil: 'networkidle' });
      await expect(page.locator('body')).toBeVisible();

      const resultado = await new AxeBuilder({ page })
        .withTags(tagsWcagAA)
        .analyze();

      persistirJson(`wcag22-incomplete-${viewport.name}.json`, resultado.incomplete);

      await testInfo.attach(`wcag22-incomplete-${viewport.name}.json`, {
        body: JSON.stringify(resultado.incomplete, null, 2),
        contentType: 'application/json',
      });

      expect(
        resultado.violations,
        JSON.stringify(resultado.violations, null, 2),
      ).toEqual([]);

      const overflow = await page.evaluate(() =>
        document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow).toBeLessThanOrEqual(1);

      const screenshot = await page.screenshot({ fullPage: true, animations: 'disabled' });
      await testInfo.attach(`visual-${viewport.name}`, {
        body: screenshot,
        contentType: 'image/png',
      });
    });
  });
}
