import { test, expect } from '@playwright/test';

/**
 * Test to verify contrast improvements in the LANbu Handy PWA
 * This test takes screenshots to document the visual accessibility improvements
 */

test.describe('Contrast Accessibility Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the PWA
    await page.goto('http://localhost:5173');

    // Wait for the page to load completely
    await page.waitForLoadState('networkidle');
  });

  test('should capture homepage with improved contrast', async ({ page }) => {
    // Take a screenshot of the main page
    await page.screenshot({
      path: 'contrast-improvements-homepage.png',
      fullPage: true,
    });

    // Verify key elements are visible
    await expect(page.getByText('LANbu Handy PWA')).toBeVisible();
    await expect(page.getByText('Self-hosted 3D printing')).toBeVisible();
  });

  test('should show improved disabled button contrast', async ({ page }) => {
    // Navigate to the slice and print section
    const sliceButton = page.getByRole('button', { name: /slice and print/i });

    // Ensure button is in disabled state (no model URL entered)
    await expect(sliceButton).toBeDisabled();

    // Take screenshot of disabled button with improved contrast
    await sliceButton.screenshot({
      path: 'improved-disabled-button-contrast.png',
    });
  });

  test('should show improved header button contrast', async ({ page }) => {
    // Take screenshot of header with improved button contrast
    await page.locator('header').screenshot({
      path: 'improved-header-button-contrast.png',
    });
  });

  test('should demonstrate accessible color combinations', async ({ page }) => {
    // Fill in a test URL to activate different states
    await page.fill(
      'input[placeholder*="URL"]',
      'https://example.com/model.stl'
    );

    // Take screenshot showing active states
    await page.screenshot({
      path: 'accessible-active-states.png',
      fullPage: true,
    });

    // Verify the button is now enabled
    const sliceButton = page.getByRole('button', { name: /slice and print/i });
    await expect(sliceButton).toBeEnabled();
  });
});

/**
 * Instructions for running this test:
 *
 * 1. Ensure the PWA development server is running on localhost:5173
 * 2. Run: npx playwright test contrast-test.spec.ts
 *
 * The test will generate screenshots showing:
 * - Overall homepage with improved contrast
 * - Disabled buttons with better text visibility
 * - Header elements with improved transparency/contrast
 * - Active states demonstrating accessible color combinations
 */
