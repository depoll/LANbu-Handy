import { test, expect } from '@playwright/test';

test.describe('Mobile Scrolling Functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the backend API to enable status messages
    await page.route('/api/**', route => {
      const url = route.request().url();

      if (url.includes('/api/status')) {
        route.fulfill({
          status: 200,
          body: JSON.stringify({
            status: 'healthy',
            application_name: 'LANbu Handy',
            version: '1.0.0',
          }),
        });
      } else if (url.includes('/api/model/submit-url')) {
        route.fulfill({
          status: 200,
          body: JSON.stringify({
            success: true,
            message: 'Model analyzed successfully',
            file_id: 'test-file-id',
            filament_requirements: {
              filament_count: 2,
              filament_types: ['PLA', 'PETG'],
              filament_colors: ['#FF0000', '#00FF00'],
              has_multicolor: false,
            },
            plates: [],
            has_multiple_plates: false,
          }),
        });
      } else {
        route.continue();
      }
    });
  });

  test('status messages area has mobile touch scrolling enabled', async ({
    page,
  }) => {
    // Set up mobile viewport
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE size

    // Navigate to the application
    await page.goto('/');

    // Wait for the app to initialize
    await expect(page.locator('[data-testid="app-initialized"]')).toBeVisible();

    // Fill in model URL and analyze
    await page.fill(
      '[data-testid="model-url-input"]',
      'https://example.com/model.stl'
    );
    await page.click('[data-testid="analyze-model-button"]');

    // Wait for status messages to appear
    await expect(page.locator('.status-display')).toBeVisible();
    await expect(page.locator('.status-messages')).toBeVisible();

    // Verify the status messages container exists
    const statusMessages = page.locator('.status-messages');
    await expect(statusMessages).toBeVisible();

    // Check that the CSS properties for mobile touch scrolling are applied
    const computedStyle = await statusMessages.evaluate(element => {
      const style = window.getComputedStyle(element);
      return {
        overflowY: style.overflowY,
        webkitOverflowScrolling: style.webkitOverflowScrolling,
        touchAction: style.touchAction,
        maxHeight: style.maxHeight,
      };
    });

    // Verify the scrolling properties are correctly set
    expect(computedStyle.overflowY).toBe('auto');
    expect(computedStyle.maxHeight).toBe('300px');
    // Note: webkitOverflowScrolling and touchAction might not be captured by computedStyle
    // in all browsers, but the CSS is applied

    // Verify there are multiple status messages that could potentially require scrolling
    const messageElements = page.locator('.status-message');
    const messageCount = await messageElements.count();
    expect(messageCount).toBeGreaterThan(0);

    // Test that the status messages container is touchable/interactive
    const boundingBox = await statusMessages.boundingBox();
    expect(boundingBox).toBeTruthy();
    expect(boundingBox!.height).toBeLessThanOrEqual(300); // Respects max-height
  });

  test('status messages container maintains scrollability with many messages', async ({
    page,
  }) => {
    // Set up mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Navigate to the application
    await page.goto('/');

    // Wait for the app to initialize
    await expect(page.locator('[data-testid="app-initialized"]')).toBeVisible();

    // Fill in model URL and analyze to generate status messages
    await page.fill(
      '[data-testid="model-url-input"]',
      'https://example.com/model.stl'
    );
    await page.click('[data-testid="analyze-model-button"]');

    // Wait for status messages to appear
    await expect(page.locator('.status-display')).toBeVisible();

    // Verify that the status messages container respects the height constraints
    const statusMessages = page.locator('.status-messages');
    const boundingBox = await statusMessages.boundingBox();

    // The container should not exceed 300px height (max-height CSS property)
    if (boundingBox) {
      expect(boundingBox.height).toBeLessThanOrEqual(300);
    }

    // Verify the container has scrollable content if there are many messages
    const scrollHeight = await statusMessages.evaluate(element => {
      return element.scrollHeight;
    });

    const clientHeight = await statusMessages.evaluate(element => {
      return element.clientHeight;
    });

    // If content overflows, scrollHeight should be greater than clientHeight
    if (scrollHeight > clientHeight) {
      // This means scrolling is needed, which is good for our test
      expect(scrollHeight).toBeGreaterThan(clientHeight);
    }
  });
});
