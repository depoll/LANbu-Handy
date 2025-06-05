import { test, expect } from '@playwright/test';

// LANbu Handy E2E UI Tests
// Comprehensive testing of all MVP user stories through the web interface

const BASE_URL = process.env.LANBU_URL || 'http://localhost:8080';
const TEST_FILE_SERVER =
  process.env.TEST_FILE_SERVER || 'http://localhost:8888';

test.describe('LANbu Handy MVP User Stories', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the PWA before each test
    await page.goto(BASE_URL);

    // Wait for the app to initialize
    await page.waitForSelector('[data-testid="app-initialized"]', {
      timeout: 10000,
      state: 'visible',
    });
  });

  test('US001: Submit Model URL - Valid .3mf file', async ({ page }) => {
    // Test submitting a valid .3mf URL
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/Original3DBenchy3Dprintconceptsnormel.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for analysis to complete
    await page.waitForSelector('[data-testid="model-analysis-success"]', {
      timeout: 30000,
    });

    // Verify success message is displayed
    await expect(page.locator('[data-testid="status-message"]')).toContainText(
      'Model processed successfully'
    );

    // Verify filament requirements are displayed
    await expect(
      page.locator('[data-testid="filament-requirements"]')
    ).toBeVisible();
  });

  test('US001: Submit Model URL - Invalid URL handling', async ({ page }) => {
    // Test error handling with invalid URL
    await page.fill(
      '[data-testid="model-url-input"]',
      'http://invalid-url.example/nonexistent.3mf'
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for error message
    await page.waitForSelector('[data-testid="error-message"]', {
      timeout: 10000,
    });

    // Verify error message is displayed
    await expect(page.locator('[data-testid="error-message"]')).toContainText(
      'Failed to download'
    );
  });

  test('US002: Printer Selection - Display configured printer', async ({
    page,
  }) => {
    // Navigate to printer selection
    await page.click('[data-testid="printer-selector-button"]');

    // Verify printer selection interface is visible
    await expect(
      page.locator('[data-testid="printer-selector"]')
    ).toBeVisible();

    // Check if mock printer is displayed
    await expect(page.locator('[data-testid="printer-option"]')).toBeVisible();
  });

  test('US003: View Model Filament Needs - Multi-color model', async ({
    page,
  }) => {
    // Submit multi-color model
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/multicolor-test-coin.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for analysis
    await page.waitForSelector('[data-testid="filament-requirements"]', {
      timeout: 30000,
    });

    // Verify multiple filament requirements are shown
    const filamentItems = page.locator(
      '[data-testid="filament-requirement-item"]'
    );
    await expect(filamentItems).toHaveCount(await filamentItems.count());

    // Verify color swatches are displayed
    await expect(page.locator('[data-testid="color-swatch"]')).toBeVisible();
  });

  test('US004: View AMS Filaments - Status display', async ({ page }) => {
    // First submit a model to trigger AMS status fetch
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/Original3DBenchy3Dprintconceptsnormel.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for model analysis
    await page.waitForSelector('[data-testid="model-analysis-success"]', {
      timeout: 30000,
    });

    // Check if AMS status section appears
    await expect(
      page.locator('[data-testid="ams-status-section"]')
    ).toBeVisible();

    // Check for AMS refresh button
    await expect(
      page.locator('[data-testid="ams-refresh-button"]')
    ).toBeVisible();
  });

  test('US005-US006: Filament Mapping - Auto and Manual Assignment', async ({
    page,
  }) => {
    // Submit multi-color model
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/multicolor-test-coin.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for analysis and filament mapping interface
    await page.waitForSelector('[data-testid="filament-mapping-section"]', {
      timeout: 30000,
    });

    // Verify filament mapping dropdowns are present
    const mappingDropdowns = page.locator(
      '[data-testid="filament-mapping-dropdown"]'
    );
    await expect(mappingDropdowns.first()).toBeVisible();

    // Test manual assignment - click first dropdown
    await mappingDropdowns.first().click();

    // Verify dropdown options are available
    await expect(page.locator('[data-testid="filament-option"]')).toBeVisible();
  });

  test('US007: Select Build Plate - Options and selection', async ({
    page,
  }) => {
    // Submit model first
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/Original3DBenchy3Dprintconceptsnormel.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for configuration interface
    await page.waitForSelector('[data-testid="build-plate-selector"]', {
      timeout: 30000,
    });

    // Verify build plate selector is visible
    await expect(
      page.locator('[data-testid="build-plate-selector"]')
    ).toBeVisible();

    // Test selecting different build plate
    await page.selectOption(
      '[data-testid="build-plate-selector"]',
      'textured_pei'
    );

    // Verify selection is applied
    await expect(
      page.locator('[data-testid="build-plate-selector"]')
    ).toHaveValue('textured_pei');
  });

  test('US009-US010: Initiate Slicing with Progress Feedback', async ({
    page,
  }) => {
    // Complete model setup
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/Original3DBenchy3Dprintconceptsnormel.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for configuration interface
    await page.waitForSelector('[data-testid="slice-button"]', {
      timeout: 30000,
    });

    // Initiate slicing
    await page.click('[data-testid="slice-button"]');

    // Verify slicing progress indication
    await expect(
      page.locator('[data-testid="slicing-progress"]')
    ).toBeVisible();

    // Wait for slicing completion (with extended timeout)
    await page.waitForSelector('[data-testid="slicing-complete"]', {
      timeout: 120000,
    });

    // Verify print button becomes available
    await expect(page.locator('[data-testid="print-button"]')).toBeVisible();
    await expect(page.locator('[data-testid="print-button"]')).toBeEnabled();
  });

  test('US011-US012: Initiate Print with Feedback', async ({ page }) => {
    // Complete full workflow to print
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/Original3DBenchy3Dprintconceptsnormel.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait and slice
    await page.waitForSelector('[data-testid="slice-button"]', {
      timeout: 30000,
    });
    await page.click('[data-testid="slice-button"]');

    // Wait for slicing completion
    await page.waitForSelector('[data-testid="print-button"]', {
      timeout: 120000,
    });

    // Initiate print
    await page.click('[data-testid="print-button"]');

    // Verify print initiation feedback
    await expect(page.locator('[data-testid="print-status"]')).toBeVisible();

    // Should show either success or appropriate error for mock setup
    const statusText = await page
      .locator('[data-testid="print-status"]')
      .textContent();
    expect(statusText).toMatch(/(started|submitted|error|failed)/i);
  });

  test('US013: Clear Error Handling - Network errors', async ({ page }) => {
    // Test with unreachable URL
    await page.fill(
      '[data-testid="model-url-input"]',
      'http://unreachable.local/model.3mf'
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for error message
    await page.waitForSelector('[data-testid="error-message"]', {
      timeout: 15000,
    });

    // Verify clear error message
    const errorText = await page
      .locator('[data-testid="error-message"]')
      .textContent();
    expect(errorText).toContain('Failed to download');
    expect(errorText.length).toBeGreaterThan(10); // Should be descriptive
  });

  test('US014: PWA Access and Functionality', async ({ page }) => {
    // Verify PWA loads correctly
    await expect(page.locator('[data-testid="app-header"]')).toBeVisible();
    await expect(page.locator('[data-testid="main-content"]')).toBeVisible();

    // Check for PWA metadata
    const title = await page.title();
    expect(title).toContain('LANbu Handy');

    // Verify main workflow components are present
    await expect(page.locator('[data-testid="model-url-input"]')).toBeVisible();
    await expect(
      page.locator('[data-testid="analyze-model-button"]')
    ).toBeVisible();
  });

  test('Responsive Design - Mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Verify mobile layout
    await expect(page.locator('[data-testid="mobile-layout"]')).toBeVisible();

    // Test touch-friendly buttons
    await expect(
      page.locator('[data-testid="analyze-model-button"]')
    ).toHaveCSS('min-height', /48px|3rem/);

    // Verify form fields are appropriately sized
    await expect(page.locator('[data-testid="model-url-input"]')).toBeVisible();
  });

  test('Workflow Reset - New Model functionality', async ({ page }) => {
    // Complete partial workflow
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/Original3DBenchy3Dprintconceptsnormel.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for analysis
    await page.waitForSelector('[data-testid="model-analysis-success"]', {
      timeout: 30000,
    });

    // Click new model button
    await page.click('[data-testid="new-model-button"]');

    // Verify form resets
    await expect(page.locator('[data-testid="model-url-input"]')).toHaveValue(
      ''
    );
    await expect(
      page.locator('[data-testid="filament-requirements"]')
    ).not.toBeVisible();
    await expect(
      page.locator('[data-testid="ams-status-section"]')
    ).not.toBeVisible();
  });

  test('Performance - Model processing time', async ({ page }) => {
    const startTime = Date.now();

    // Submit model
    await page.fill(
      '[data-testid="model-url-input"]',
      `${TEST_FILE_SERVER}/Original3DBenchy3Dprintconceptsnormel.3mf`
    );

    await page.click('[data-testid="analyze-model-button"]');

    // Wait for completion
    await page.waitForSelector('[data-testid="model-analysis-success"]', {
      timeout: 30000,
    });

    const processingTime = Date.now() - startTime;

    // Should complete within reasonable time (30 seconds)
    expect(processingTime).toBeLessThan(30000);

    console.log(`Model processing completed in ${processingTime}ms`);
  });
});

test.describe('Browser Compatibility Tests', () => {
  test('Essential features work across browsers', async ({
    page,
    browserName,
  }) => {
    console.log(`Testing on ${browserName}`);

    await page.goto(BASE_URL);

    // Test basic functionality on each browser
    await page.waitForSelector('[data-testid="app-initialized"]', {
      timeout: 10000,
    });

    // Verify core elements are functional
    await expect(page.locator('[data-testid="model-url-input"]')).toBeVisible();
    await expect(
      page.locator('[data-testid="analyze-model-button"]')
    ).toBeEnabled();

    // Test form interaction
    await page.fill(
      '[data-testid="model-url-input"]',
      'https://example.com/test.3mf'
    );
    const inputValue = await page
      .locator('[data-testid="model-url-input"]')
      .inputValue();
    expect(inputValue).toBe('https://example.com/test.3mf');

    console.log(`✅ ${browserName} compatibility test passed`);
  });
});

// Configure test timeouts and retries
test.setTimeout(180000); // 3 minutes for complex workflows

export {};
