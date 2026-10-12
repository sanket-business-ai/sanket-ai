import { expect, test } from '@playwright/test'

test('a founder can investigate, inspect evidence, challenge, and approve an action', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Email address').fill('founder@sanketai.local')
  await page.getByLabel('Password', { exact: true }).fill('e2e-only-password-12345')
  await page.getByRole('button', { name: 'Sign in to workspace' }).click()
  await expect(page.getByRole('heading', { name: 'Your business, understood.' })).toBeVisible()
  await page.getByRole('button', { name: 'Load demo evidence' }).click()
  await expect(page.getByText('Recognized revenue', { exact: true })).toBeVisible()
  await page.screenshot({ path: '../.cache/dashboard-desktop.png', fullPage: true })
  await page
    .getByLabel('Ask a business question')
    .fill('Why did our sales drop in the latest month?')
  await page.getByRole('button', { name: 'Investigate', exact: true }).click()
  await expect(page.getByText('STRONGEST SUPPORTED EXPLANATION')).toBeVisible({ timeout: 30000 })
  await expect(page.getByText('Deterministic evidence analysis', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: /^Evidence/ }).click()
  await page
    .getByRole('button', { name: /himalayanmart_orders.csv/ })
    .first()
    .click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'revenue', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Close dialog' }).click()
  await page.getByRole('tab', { name: /^Hypotheses/ }).click()
  await expect(page.getByText('Reduced demand caused the decline', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: 'Report', exact: true }).click()
  await page.getByRole('button', { name: 'Review & approve' }).click()
  await page.getByRole('button', { name: 'Approve & create task' }).click()
  await expect(page.getByText('monitoring', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Check outcome' }).click()
  await expect(page.getByRole('alert')).toContainText('newer 28-day outcome period')
  await page.getByRole('button', { name: 'Challenge conclusion', exact: true }).first().click()
  await expect(page.getByText('Adversarial pass completed', { exact: true })).toBeVisible({
    timeout: 30000,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await page.getByRole('dialog').getByRole('link', { name: 'Overview', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your business, understood.' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: '../.cache/dashboard-mobile.png', fullPage: true })
  expect(errors).toEqual([])
})
