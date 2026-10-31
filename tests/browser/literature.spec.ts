import { test, expect } from '@playwright/test';

test('literature tool works on mobile and keeps selections while filtering', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const response = await page.goto('/literatur-tarama/');
  expect(response?.status()).toBe(200);
  await page.getByLabel('Anahtar kelimeler (her satıra bir sorgu)').fill('SOC alert scheduling');
  await page.getByRole('button', { name: 'Arama URL’lerini Oluştur' }).click();
  await expect(page.locator('#rows tr')).toHaveCount(5);
  const first = page.locator('#rows .pick').first();
  await first.check();
  await page.getByRole('textbox', { name: 'Sonuçlarda filtrele' }).fill('DergiPark');
  await expect(page.locator('#rows tr')).toHaveCount(1);
  await page.getByRole('textbox', { name: 'Sonuçlarda filtrele' }).clear();
  await expect(page.locator('#rows .pick').first()).toBeChecked();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
