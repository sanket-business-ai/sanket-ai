import { expect, test } from '@playwright/test'

test('a founder can investigate, inspect evidence, challenge, and approve an action', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.screenshot({ path: '../.cache/login-desktop.png', fullPage: true })
  await page.getByRole('button', { name: 'Use dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.screenshot({ path: '../.cache/login-dark.png', fullPage: true })
  await page.getByRole('button', { name: 'Use light theme' }).click()
  await page.getByLabel('Email address').fill('founder@sanketai.local')
  await page.getByLabel('Password', { exact: true }).fill('e2e-only-password-12345')
  await page.getByRole('button', { name: 'Sign in to workspace' }).click()
  await expect(page.getByRole('heading', { name: 'Your business, understood.' })).toBeVisible()
  await page.getByRole('button', { name: 'Load demo evidence' }).click()
  await expect(page.getByText('Recognized revenue', { exact: true })).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  expect(await page.evaluate(() => document.fonts.check('600 16px Figtree'))).toBe(true)
  expect(await page.locator('body').evaluate((el) => getComputedStyle(el).fontFamily)).toContain(
    'Figtree',
  )
  await page.screenshot({ path: '../.cache/dashboard-desktop.png', fullPage: true })
  await page
    .getByLabel('Ask a business question')
    .fill('Why did our sales drop in the latest month?')
  await page.getByRole('button', { name: 'Investigate', exact: true }).click()
  await expect(page.getByText('STRONGEST SUPPORTED EXPLANATION', { exact: true })).toBeVisible({
    timeout: 30000,
  })
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
  await expect(
    page.getByRole('heading', { name: 'H2 Reduced demand caused the decline', exact: true }),
  ).toBeVisible()
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
  const reportPath = new URL(page.url()).pathname
  await page.setViewportSize({ width: 1440, height: 1000 })
  for (const theme of ['light', 'dark']) {
    for (const path of [reportPath, '/', '/investigations', '/sources', '/actions', '/workspace']) {
      await page.goto(path)
      await expect(page.locator('main h1')).toBeVisible()
      await expect(
        page.getByRole('status', { name: '' }).filter({ hasText: 'Loading workspace' }),
      ).toHaveCount(0)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      const name = path === reportPath ? 'report' : path.replaceAll('/', '') || 'overview'
      // A reload resets to light; switch explicitly to verify each real page in dark mode.
      if (theme === 'dark') await page.getByRole('button', { name: 'Use dark theme' }).click()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await page.screenshot({ path: `../.cache/${name}-${theme}.png`, fullPage: true })
    }
  }
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await page.getByRole('dialog').getByRole('link', { name: 'Overview', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your business, understood.' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: '../.cache/dashboard-mobile.png', fullPage: true })
  for (const width of [320, 768]) {
    await page.setViewportSize({ width, height: 900 })
    for (const path of [reportPath, '/investigations', '/sources', '/actions', '/workspace']) {
      await page.goto(path)
      await expect(page.locator('main h1')).toBeVisible()
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        `${path} at ${width}px`,
      ).toBe(true)
      if (width === 320) {
        const name = path === reportPath ? 'report' : path.slice(1)
        await page.screenshot({ path: `../.cache/${name}-mobile.png`, fullPage: true })
      }
    }
  }
  expect(errors).toEqual([])
})

test('a margin investigation shows where the contribution went', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.getByLabel('Email address').fill('founder@sanketai.local')
  await page.getByLabel('Password', { exact: true }).fill('e2e-only-password-12345')
  await page.getByRole('button', { name: 'Sign in to workspace' }).click()
  await expect(page.getByRole('heading', { name: 'Your business, understood.' })).toBeVisible()
  // Demo packs load only into an empty workspace; the first test leaves the supply demo behind.
  const loadMargin = page.getByRole('button', { name: 'Load margin demo' })
  if (!(await loadMargin.isVisible())) {
    await page.goto('/sources')
    await page.getByRole('button', { name: 'Clear workspace' }).click()
    await page.getByRole('button', { name: 'Clear everything' }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await page.goto('/')
  }
  await loadMargin.click()
  await expect(page.getByText('Recognized revenue', { exact: true })).toBeVisible()
  await page.getByLabel('Ask a business question').fill('Why is our margin falling?')
  await page.getByRole('button', { name: 'Investigate', exact: true }).click()
  const chart = page.getByRole('list', { name: 'Contribution bridge' })
  await expect(chart).toBeVisible({ timeout: 30000 })
  await expect(page.getByRole('heading', { name: 'Where the margin went' })).toBeVisible()
  await expect(chart.getByText('Courier fees', { exact: true })).toBeVisible()
  await expect(chart.getByText('Baseline contribution', { exact: true })).toBeVisible()
  await expect(chart.getByText('Current contribution', { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 1440, height: 1000 })
  const card = page.locator('.rounded-xl, [class*="card"]').filter({ has: chart }).last()
  await card.screenshot({ path: '../.cache/margin-chart-light.png' })
  await page.getByRole('button', { name: 'Use dark theme' }).click()
  await card.screenshot({ path: '../.cache/margin-chart-dark.png' })
  await page.setViewportSize({ width: 320, height: 900 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await card.screenshot({ path: '../.cache/margin-chart-mobile.png' })
  await chart.getByRole('button', { name: /Courier fees/ }).click()
  await expect(page.getByRole('tab', { name: /^Evidence/ })).toHaveAttribute('data-state', 'active')
  expect(errors).toEqual([])
})
