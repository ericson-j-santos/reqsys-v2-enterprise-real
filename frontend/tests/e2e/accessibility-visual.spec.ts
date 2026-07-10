import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:4173';

for (const viewport of [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
]) {
  test.describe(`qualidade visual ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test('não possui violações críticas e mantém baseline visual', async ({ page }) => {
      await page.goto(baseURL, { waitUntil: 'networkidle' });
      await expect(page.locator('body')).toBeVisible();

      const resultado = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze();

      const criticas = resultado.violations.filter((item) =>
        ['critical', 'serious'].includes(item.impact || ''),
      );
      expect(criticas, JSON.stringify(criticas, null, 2)).toEqual([]);

      await expect(page).toHaveScreenshot(`home-${viewport.name}.png`, {
        fullPage: true,
        animations: 'disabled',
        maxDiffPixelRatio: 0.01,
      });
    });
  });
}
