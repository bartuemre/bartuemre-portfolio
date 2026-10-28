import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const routes = ['/', '/about/', '/projects/', '/projects/soc-decision-lab/', '/projects/research-explorer/', '/contact/', '/lab/', '/blog/', '/404.html'];

for (const theme of ['dark', 'light'] as const) {
  test(`${theme}: all pages, accessibility, metadata, and browser errors`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme });
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('requestfailed', (request) => errors.push(request.url()));
    for (const route of routes) {
      const response = await page.goto(route);
      expect(response?.status()).toBe(200);
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
      await expect(page.locator('h1')).toHaveCount(1);
      await expect(page.locator('meta[property="og:title"]')).toHaveAttribute('content', await page.title());
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      expect(results.violations, `${route}: ${JSON.stringify(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })))}`).toEqual([]);
    }
    expect(errors).toEqual([]);
  });
}

for (const width of [320, 390, 768, 1440]) {
  test(`responsive layout at ${width}px across every route`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const route of routes) {
      await page.goto(route);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), route).toBe(true);
      await expect(page.locator('h1')).toBeVisible();
    }
  });
}

test('theme follows system initially and persists an explicit choice across reloads and routes', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('navigation').getByRole('link', { name: 'About', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('navigation').getByRole('link', { name: 'About', exact: true })).toHaveAttribute('aria-current', 'page');
});

test('mobile navigation supports keyboard, Escape, active links, and resize', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const button = page.getByRole('button', { name: 'Open navigation' });
  await expect(page.getByRole('navigation')).toBeHidden();
  await button.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('navigation')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(button).toBeFocused();
  await expect(page.getByRole('navigation')).toBeHidden();
  await button.click();
  await page.getByRole('navigation').getByRole('link', { name: 'Projects', exact: true }).click();
  await expect(page).toHaveURL(/\/projects\/$/);
  await expect(page.getByRole('navigation')).toBeHidden();
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.getByRole('navigation')).toBeVisible();
  await expect(page.locator('#menu-toggle')).toBeHidden();
  await expect(page.getByRole('navigation').getByRole('link', { name: 'Projects', exact: true })).toHaveAttribute('aria-current', 'page');
});

test('skip link moves keyboard focus to main content', async ({ page }) => {
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
});

test('theme and navigation still work if browser storage is blocked', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new Error('Storage unavailable'); } });
  });
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  await page.getByRole('button', { name: 'Switch to light theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});

test('no-JavaScript fallback exposes content and mobile navigation', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 320, height: 800 }, colorScheme: 'dark' });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4321/');
  await expect(page.getByRole('navigation')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'SOC Decision Lab' })).toBeVisible();
  await expect(page.locator('#theme-toggle')).toBeHidden();
  await page.getByRole('navigation').getByRole('link', { name: 'Projects', exact: true }).click();
  await expect(page).toHaveURL(/\/projects\/$/);
  await context.close();
});

test('reduced motion removes animation and leaves content visible', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  expect(await page.locator('.orbit-ring').evaluate((el) => getComputedStyle(el).animationName)).toBe('none');
  expect(await page.locator('.project-card').first().evaluate((el) => getComputedStyle(el).opacity)).toBe('1');
});

test('project detail navigation and unavailable links', async ({ page }) => {
  await page.goto('/projects/');
  await page.getByRole('link', { name: 'Research Explorer', exact: true }).click();
  await expect(page.getByText('Repository link not yet available.')).toBeVisible();
  await expect(page.getByRole('link', { name: /View repository/ })).toHaveCount(0);
  await page.goto('/projects/soc-decision-lab/');
  await expect(page.getByRole('link', { name: /View repository/ })).toHaveAttribute('href', 'https://github.com/bartuemre/soc-decision-lab');
});

test('unknown paths return a custom 404', async ({ page }) => {
  const response = await page.goto('/this-page-does-not-exist/');
  expect(response?.status()).toBe(404);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('No signal');
});

test('capture desktop and mobile review images', async ({ page }, testInfo) => {
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await page.screenshot({ path: testInfo.outputPath('home-dark-desktop.png'), fullPage: true });
  await page.getByRole('button', { name: 'Switch to light theme' }).click();
  await page.screenshot({ path: testInfo.outputPath('home-light-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Switch to dark theme' }).click();
  await page.screenshot({ path: testInfo.outputPath('home-dark-mobile.png'), fullPage: true });
});
