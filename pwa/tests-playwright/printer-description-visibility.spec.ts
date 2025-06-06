import { test, expect } from '@playwright/test';

/**
 * Test to verify the printer description visibility fix in the LANbu Handy PWA header
 * This test documents the fix for white text on white background issue
 */

test.describe('Printer Description Visibility Fix', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the PWA
    await page.goto('http://localhost:5173');

    // Wait for the page to load completely
    await page.waitForLoadState('networkidle');
  });

  test('should show visible printer description text in header', async ({
    page,
  }) => {
    // Take a screenshot of the header area
    await page.locator('header').screenshot({
      path: 'header-printer-selector-visibility-fix.png',
    });

    // Verify the header printer selector exists
    const printerSelector = page.locator('.header-printer-selector');
    await expect(printerSelector).toBeVisible();

    // Verify that printer description elements exist (even if no printer is selected)
    const printerDisplay = page.locator('.current-printer-display');
    await expect(printerDisplay).toBeVisible();

    // Check that the "No printer selected" text is visible
    const noPrinterText = page.locator('.no-printer-text');
    if (await noPrinterText.isVisible()) {
      await expect(noPrinterText).toHaveCSS('color', 'rgb(255, 205, 210)'); // #ffcdd2
    }
  });

  test('should have improved background contrast for printer selector', async ({
    page,
  }) => {
    // Check the current printer display has the updated background
    const currentPrinterDisplay = page.locator(
      '.header-printer-selector .current-printer-display'
    );
    await expect(currentPrinterDisplay).toBeVisible();

    // The background should now be rgba(255, 255, 255, 0.15) instead of rgba(255, 255, 255, 0.05)
    // This provides better contrast for white text
    const backgroundStyle = await currentPrinterDisplay.evaluate(
      el => window.getComputedStyle(el).backgroundColor
    );

    // We expect a more opaque white background
    expect(backgroundStyle).toMatch(/rgba?\(255,\s*255,\s*255,\s*0\.1[5-9]/);
  });
});

/**
 * Instructions for running this test:
 *
 * 1. Ensure the PWA development server is running on localhost:5173
 * 2. Run: npx playwright test printer-description-visibility.spec.ts
 *
 * The test will verify:
 * - Printer description text has sufficient contrast in the header
 * - Background opacity has been increased for better visibility
 * - Screenshots document the improved visibility
 */
