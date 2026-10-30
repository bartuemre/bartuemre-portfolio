import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('language switch preserves the page and translated navigation stays in Turkish', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#selected-work')).toHaveCount(0);
  await page.getByRole('link', { name: 'Türkçe', exact: true }).click();
  await expect(page).toHaveURL('/tr/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'tr');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Doğamda merak var.');
  await page.getByRole('navigation').getByRole('link', { name: 'Projeler', exact: true }).click();
  await expect(page).toHaveURL('/tr/projects/');
  await expect(page.locator('#selected-work')).toBeVisible();
  await expect(page.locator('.project-card')).toHaveCount(3);
  const popup = page.waitForEvent('popup');
  await page.getByRole('link', { name: 'SOC Decision Lab projesini yeni sekmede aç' }).click();
  const detail = await popup;
  await expect(detail).toHaveURL('/tr/projects/soc-decision-lab/');
  await expect(detail.getByRole('heading', { name: 'Yaklaşım', exact: true })).toBeVisible();
  await detail.getByRole('link', { name: 'English', exact: true }).click();
  await expect(detail).toHaveURL('/projects/soc-decision-lab/');
  await expect(detail.locator('html')).toHaveAttribute('lang', 'en');
});

test('Turkish mobile controls and language links work with blocked storage', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } }));
  await page.setViewportSize({ width: 320, height: 850 });
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto('/tr/');
  await page.getByRole('button', { name: 'Koyu temaya geç' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: 'Menüyü aç' }).click();
  await page.getByRole('navigation').getByRole('link', { name: 'Hakkımda' }).click();
  await expect(page).toHaveURL('/tr/about/');
  await page.getByRole('link', { name: 'English', exact: true }).click();
  await expect(page).toHaveURL('/about/');
});

test('language links work without JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4321/projects/research-explorer/');
  await page.getByRole('link', { name: 'Türkçe', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'tr');
  await expect(page.getByRole('heading', { name: 'Güncel durum', exact: true })).toBeVisible();
  await context.close();
});

test('Turkish pages fit mobile and desktop; shared controls remain accessible', async ({ page }, testInfo) => {
  const routes = ['/', '/about/', '/projects/', '/projects/soc-decision-lab/', '/projects/research-explorer/', '/projects/iprv/', '/lab/', '/blog/', '/contact/', '/404/'];
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const width of [320, 390, 768, 820, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of routes) {
      await page.goto(`/tr${route}`);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}: ${route}`).toBe(true);
      await expect(page.getByRole('link', { name: 'English', exact: true })).toBeInViewport();
    }
  }
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme });
    await page.goto('/tr/');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  }
  await page.screenshot({ path: testInfo.outputPath('home-tr-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: testInfo.outputPath('home-tr-mobile.png'), fullPage: true });
  await page.goto('/tr/projects/');
  await page.screenshot({ path: testInfo.outputPath('projects-tr-mobile.png'), fullPage: true });
});
