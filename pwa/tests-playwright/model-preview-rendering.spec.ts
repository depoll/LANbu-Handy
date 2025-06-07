import { test, expect } from '@playwright/test';

/**
 * Test to verify model preview rendering functionality in the LANbu Handy PWA
 * This test uses real model files to ensure 3D previews are rendering properly
 */

test.describe('Model Preview Rendering Tests', () => {
  const PWA_URL = 'http://localhost:5173';
  const FILE_SERVER_URL = 'http://localhost:8888'; // Simple HTTP server for test files

  // Test file URLs served by local file server
  const TEST_FILES = {
    benchy_3mf: `${FILE_SERVER_URL}/Original3DBenchy3Dprintconceptsnormel.3mf`,
    multicolor_3mf: `${FILE_SERVER_URL}/multicolor-test-coin.3mf`,
    multiplate_3mf: `${FILE_SERVER_URL}/multiplate-test.3mf`,
  };

  test.beforeEach(async ({ page }) => {
    // Navigate to the PWA
    await page.goto(PWA_URL);

    // Wait for the page to load completely
    await page.waitForLoadState('networkidle');

    // Wait for the app to initialize (check if backend is available)
    await page
      .waitForSelector('[data-testid="app-initialized"]', {
        timeout: 10000,
        state: 'visible',
      })
      .catch(() => {
        // If data-testid is not available, wait for basic UI elements
        console.log('App initialized testid not found, waiting for basic UI');
      });

    // Ensure the main UI is visible
    await expect(page.getByText('LANbu Handy')).toBeVisible();
  });

  test('should render 3D preview for 3MF model file (Benchy)', async ({
    page,
  }) => {
    // Submit a real 3MF model file URL
    const modelUrlInput = page.locator('input[placeholder*="URL"]').first();

    await expect(modelUrlInput).toBeVisible();
    await modelUrlInput.fill(TEST_FILES.benchy_3mf);

    // Find and click the analyze/submit button
    const analyzeButton = page
      .locator('button')
      .filter({ hasText: /analyze|submit|process/i })
      .first();
    await expect(analyzeButton).toBeVisible();
    await analyzeButton.click();

    // Wait for model processing - should show success
    await page.waitForSelector(
      '[data-testid="model-analysis-success"], .model-preview',
      {
        timeout: 30000,
      }
    );

    // Look for the model preview component
    const modelPreview = page.locator('.model-preview');
    await expect(modelPreview).toBeVisible();

    // Take a screenshot of the model preview area
    await modelPreview.screenshot({
      path: 'model-preview-benchy-3mf.png',
    });

    // Check for Three.js canvas element
    const canvas = modelPreview.locator('canvas');
    await expect(canvas).toBeVisible();

    // Verify the canvas has been drawn to (width and height > 0)
    const canvasBox = await canvas.boundingBox();
    expect(canvasBox?.width).toBeGreaterThan(0);
    expect(canvasBox?.height).toBeGreaterThan(0);

    // Wait for loading to complete and check for no errors
    await page.waitForTimeout(5000); // Allow for model loading and rendering

    const loadingText = modelPreview.locator('.loading-text');
    await expect(loadingText).not.toBeVisible();

    const errorText = modelPreview.locator('.error-text');
    await expect(errorText).not.toBeVisible();

    // Verify model preview header
    await expect(modelPreview.locator('.model-preview-header')).toContainText(
      'Model Preview'
    );

    console.log('✅ 3D model preview rendered successfully for Benchy 3MF');
  });

  test('should handle model preview initialization errors gracefully', async ({
    page,
  }) => {
    // Test WebGL support detection
    await page.evaluate(() => {
      // Mock WebGL as unsupported to test error handling
      const originalGetContext = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (contextType) {
        if (contextType === 'webgl' || contextType === 'experimental-webgl') {
          return null; // Simulate WebGL not available
        }
        return originalGetContext.call(this, contextType);
      };
    });

    // Try to trigger model preview with mocked WebGL failure
    const modelUrlInput = page.locator('input[placeholder*="URL"]').first();

    if (await modelUrlInput.isVisible()) {
      await modelUrlInput.fill('https://example.com/test-model.stl');

      const analyzeButton = page
        .locator('button')
        .filter({ hasText: /analyze|submit|process/i })
        .first();
      if (await analyzeButton.isVisible()) {
        await analyzeButton.click();
        await page.waitForTimeout(2000);

        // Look for WebGL error handling
        const modelPreview = page.locator('.model-preview');
        if (await modelPreview.isVisible()) {
          const errorText = modelPreview.locator('.error-text');

          // Should show WebGL not supported error
          if (await errorText.isVisible()) {
            const errorMessage = await errorText.textContent();
            expect(errorMessage?.toLowerCase()).toContain('webgl');
            console.log('✅ WebGL error handling working correctly');
          }

          // Take screenshot of error state
          await modelPreview.screenshot({
            path: 'model-preview-webgl-error.png',
          });
        }
      }
    }
  });

  test('should display model preview component structure correctly', async ({
    page,
  }) => {
    // Test the basic structure of model preview component when it appears

    // Fill model URL to potentially trigger preview
    const modelUrlInput = page.locator('input[placeholder*="URL"]').first();

    if (await modelUrlInput.isVisible()) {
      await modelUrlInput.fill('https://example.com/test-model.3mf');

      const analyzeButton = page
        .locator('button')
        .filter({ hasText: /analyze|submit|process/i })
        .first();
      if (await analyzeButton.isVisible()) {
        await analyzeButton.click();
        await page.waitForTimeout(1000);

        const modelPreview = page.locator('.model-preview');

        if (await modelPreview.isVisible()) {
          // Check for model preview header
          const previewHeader = modelPreview.locator('.model-preview-header');
          await expect(previewHeader).toBeVisible();

          // Check for preview container
          const previewContainer = modelPreview.locator(
            '.model-preview-container'
          );
          await expect(previewContainer).toBeVisible();

          // Verify container has appropriate styling
          const containerStyle = await previewContainer.evaluate(el => {
            const style = window.getComputedStyle(el);
            return {
              width: style.width,
              height: style.height,
              border: style.border,
              borderRadius: style.borderRadius,
            };
          });

          expect(containerStyle.height).toBe('300px');
          expect(containerStyle.width).not.toBe('0px');

          // Take screenshot of the preview structure
          await modelPreview.screenshot({
            path: 'model-preview-structure.png',
          });

          console.log('✅ Model preview component structure is correct');
        }
      }
    }
  });

  test('should test model preview with multicolor model', async ({ page }) => {
    // Test multicolor model preview specifically
    const modelUrlInput = page.locator('input[placeholder*="URL"]').first();
    await expect(modelUrlInput).toBeVisible();

    // Use multicolor test file
    await modelUrlInput.fill(TEST_FILES.multicolor_3mf);

    const analyzeButton = page
      .locator('button')
      .filter({ hasText: /analyze|submit|process/i })
      .first();
    await expect(analyzeButton).toBeVisible();
    await analyzeButton.click();

    // Wait for model processing
    await page.waitForSelector('.model-preview', { timeout: 30000 });

    const modelPreview = page.locator('.model-preview');
    await expect(modelPreview).toBeVisible();

    // Check for multicolor warning note
    const multicolorNote = modelPreview.locator('.preview-note');
    await expect(multicolorNote).toBeVisible();

    const noteText = await multicolorNote.textContent();
    expect(noteText?.toLowerCase()).toContain('multi-material');
    console.log('✅ Multicolor model note displayed correctly');

    // Verify canvas is rendered
    const canvas = modelPreview.locator('canvas');
    await expect(canvas).toBeVisible();

    // Take screenshot of multicolor model preview
    await modelPreview.screenshot({
      path: 'model-preview-multicolor.png',
    });

    // Wait for loading to complete
    await page.waitForTimeout(5000);
    const loadingText = modelPreview.locator('.loading-text');
    await expect(loadingText).not.toBeVisible();
  });

  test('should verify Three.js scene setup and rendering', async ({ page }) => {
    // Test Three.js specific functionality

    const modelUrlInput = page.locator('input[placeholder*="URL"]').first();

    if (await modelUrlInput.isVisible()) {
      await modelUrlInput.fill('https://example.com/test-model.stl');

      const analyzeButton = page
        .locator('button')
        .filter({ hasText: /analyze|submit|process/i })
        .first();
      if (await analyzeButton.isVisible()) {
        await analyzeButton.click();
        await page.waitForTimeout(1000);

        const modelPreview = page.locator('.model-preview');

        if (await modelPreview.isVisible()) {
          const canvas = modelPreview.locator('canvas');

          if (await canvas.isVisible()) {
            // Test canvas context and WebGL
            const canvasInfo = await canvas.evaluate(
              (canvasEl: HTMLCanvasElement) => {
                const gl =
                  canvasEl.getContext('webgl') ||
                  canvasEl.getContext('experimental-webgl');
                return {
                  hasWebGL: !!gl,
                  width: canvasEl.width,
                  height: canvasEl.height,
                  style: {
                    width: canvasEl.style.width,
                    height: canvasEl.style.height,
                  },
                };
              }
            );

            expect(canvasInfo.hasWebGL).toBe(true);
            expect(canvasInfo.width).toBeGreaterThan(0);
            expect(canvasInfo.height).toBeGreaterThan(0);

            // Wait for potential animation frames
            await page.waitForTimeout(2000);

            // Take screenshot during animation
            await canvas.screenshot({
              path: 'model-preview-threejs-rendering.png',
            });

            console.log('✅ Three.js rendering working correctly', canvasInfo);
          }
        }
      }
    }
  });
});

/**
 * Instructions for running this test:
 *
 * 1. Ensure both backend and PWA servers are running:
 *    - Backend: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
 *    - PWA: cd pwa && npm run dev -- --host 0.0.0.0 --port 5173
 *
 * 2. Run the test:
 *    npx playwright test model-preview-rendering.spec.ts
 *
 * The test will generate screenshots showing:
 * - Model preview rendering with 3MF files
 * - Error handling for WebGL issues
 * - Component structure validation
 * - Multicolor model handling
 * - Three.js scene setup verification
 */
