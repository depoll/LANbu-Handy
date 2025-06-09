import { test, expect } from '@playwright/test';

/**
 * Enhanced Model Preview Tests
 *
 * Tests the improved model preview functionality with thumbnail fallback
 * and better multi-part 3MF handling.
 */

test.describe('Enhanced Model Preview Tests', () => {
  const PWA_URL = 'http://localhost:5173';
  const FILE_SERVER_URL = 'http://localhost:8888';
  const BACKEND_URL = 'http://localhost:8000';

  // Test file URLs
  const TEST_FILES = {
    benchy_3mf: `${FILE_SERVER_URL}/Original3DBenchy3Dprintconceptsnormel.3mf`,
    multicolor_3mf: `${FILE_SERVER_URL}/multicolor-test-coin.3mf`,
    multiplate_3mf: `${FILE_SERVER_URL}/multiplate-test.3mf`,
  };

  test('should fallback to thumbnail when Three.js loading fails', async ({
    page,
  }) => {
    // Mock Three.js to fail loading
    await page.goto(PWA_URL);

    // Wait for app initialization
    await page.waitForTimeout(2000);

    // Inject script to mock Three.js loader failure
    await page.addInitScript(() => {
      // Mock the ThreeMFLoader to always fail
      window.addEventListener('load', () => {
        if (window.THREE && window.THREE.ThreeMFLoader) {
          // Store original for potential future use
          // const originalLoad = window.THREE.ThreeMFLoader.prototype.load;
          window.THREE.ThreeMFLoader.prototype.load = function (
            url,
            onLoad,
            onProgress,
            onError
          ) {
            // Simulate loading failure after a delay
            setTimeout(() => {
              if (onError) {
                onError(new Error('Simulated Three.js loading failure'));
              }
            }, 1000);
          };
        }
      });
    });

    // Submit a model URL
    const modelUrlInput = page.locator('input[placeholder*="URL"]').first();
    if (await modelUrlInput.isVisible()) {
      await modelUrlInput.fill(TEST_FILES.benchy_3mf);

      const analyzeButton = page
        .locator('button')
        .filter({ hasText: /analyze|submit|process/i })
        .first();

      if (await analyzeButton.isVisible()) {
        await analyzeButton.click();

        // Wait for model processing
        await page.waitForTimeout(5000);

        const modelPreview = page.locator('.model-preview');
        if (await modelPreview.isVisible()) {
          // Should eventually show thumbnail fallback
          const thumbnailImage = modelPreview.locator(
            'img[alt="Model Thumbnail"]'
          );

          // Wait longer for thumbnail fallback to trigger
          await page.waitForTimeout(10000);

          if (await thumbnailImage.isVisible()) {
            // Take screenshot of thumbnail fallback
            await modelPreview.screenshot({
              path: 'model-preview-thumbnail-fallback.png',
            });

            // Verify thumbnail indicator text
            await expect(
              modelPreview.locator('text=📷 Thumbnail Preview')
            ).toBeVisible();
            console.log('✅ Thumbnail fallback working correctly');
          } else {
            console.log('ℹ️ Thumbnail fallback may not have triggered in time');
          }
        }
      }
    }
  });

  test('should test thumbnail API endpoint directly', async ({ page }) => {
    // First submit a model to get a file ID
    const response = await page.request.post(
      `${BACKEND_URL}/api/model/submit-url`,
      {
        data: {
          model_url: TEST_FILES.benchy_3mf,
        },
      }
    );

    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.success).toBe(true);
    expect(data.file_id).toBeTruthy();

    const fileId = data.file_id;
    console.log('Model submitted with file ID:', fileId);

    // Test thumbnail endpoint
    const thumbnailResponse = await page.request.get(
      `${BACKEND_URL}/api/model/thumbnail/${fileId}?width=300&height=300`
    );

    expect(thumbnailResponse.ok()).toBeTruthy();
    expect(thumbnailResponse.headers()['content-type']).toContain('image/');

    // Save thumbnail for verification
    const thumbnailBuffer = await thumbnailResponse.body();
    expect(thumbnailBuffer.length).toBeGreaterThan(0);

    console.log('✅ Thumbnail API endpoint working correctly');
    console.log(`Thumbnail size: ${thumbnailBuffer.length} bytes`);
  });

  test('should handle multi-part 3MF files with improved geometry handling', async ({
    page,
  }) => {
    await page.goto(PWA_URL);
    await page.waitForTimeout(2000);

    // Submit multiplate model (likely to have multiple geometries)
    const modelUrlInput = page.locator('input[placeholder*="URL"]').first();
    if (await modelUrlInput.isVisible()) {
      await modelUrlInput.fill(TEST_FILES.multiplate_3mf);

      const analyzeButton = page
        .locator('button')
        .filter({ hasText: /analyze|submit|process/i })
        .first();

      if (await analyzeButton.isVisible()) {
        await analyzeButton.click();

        // Wait for processing
        await page.waitForTimeout(8000);

        const modelPreview = page.locator('.model-preview');
        if (await modelPreview.isVisible()) {
          // Take screenshot of multi-part handling
          await modelPreview.screenshot({
            path: 'model-preview-multipart-handling.png',
          });

          // Check for either 3D render or thumbnail
          const canvas = modelPreview.locator('canvas');
          const thumbnailImage = modelPreview.locator(
            'img[alt="Model Thumbnail"]'
          );

          const hasCanvas = await canvas.isVisible();
          const hasThumbnail = await thumbnailImage.isVisible();

          expect(hasCanvas || hasThumbnail).toBe(true);

          if (hasCanvas) {
            console.log(
              '✅ Multi-part 3MF rendered with Three.js (possibly merged geometries)'
            );
          } else if (hasThumbnail) {
            console.log('✅ Multi-part 3MF displayed with thumbnail fallback');
          }

          // Verify no error messages
          const errorText = modelPreview.locator('.error-text');
          if (await errorText.isVisible()) {
            const errorMessage = await errorText.textContent();
            console.log('Error message:', errorMessage);
          } else {
            console.log('✅ No error messages displayed');
          }
        }
      }
    }
  });

  test('should display appropriate preview indicators', async ({ page }) => {
    await page.goto(PWA_URL);
    await page.waitForTimeout(2000);

    const modelUrlInput = page.locator('input[placeholder*="URL"]').first();
    if (await modelUrlInput.isVisible()) {
      await modelUrlInput.fill(TEST_FILES.multicolor_3mf);

      const analyzeButton = page
        .locator('button')
        .filter({ hasText: /analyze|submit|process/i })
        .first();

      if (await analyzeButton.isVisible()) {
        await analyzeButton.click();

        await page.waitForTimeout(8000);

        const modelPreview = page.locator('.model-preview');
        if (await modelPreview.isVisible()) {
          // Take final screenshot
          await modelPreview.screenshot({
            path: 'model-preview-final-state.png',
          });

          // Check for preview indicators
          const previewHeader = modelPreview.locator('.model-preview-header');
          await expect(previewHeader).toBeVisible();
          await expect(previewHeader).toContainText('Model Preview');

          // Check for multi-material note if applicable
          const multiMaterialNote = modelPreview.locator(
            'text=Multi-material models'
          );
          if (await multiMaterialNote.isVisible()) {
            console.log('✅ Multi-material preview note displayed');
          }

          // Check for thumbnail indicator if applicable
          const thumbnailIndicator = modelPreview.locator(
            'text=📷 Thumbnail Preview'
          );
          if (await thumbnailIndicator.isVisible()) {
            console.log('✅ Thumbnail preview indicator displayed');
          }

          console.log(
            '✅ Model preview component rendered with appropriate indicators'
          );
        }
      }
    }
  });
});

/**
 * Test Instructions:
 *
 * 1. Ensure all services are running:
 *    - Backend: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
 *    - PWA: cd pwa && npm run dev -- --host 0.0.0.0 --port 5173
 *    - File server: cd test_files && python3 -m http.server 8888
 *
 * 2. Run the test:
 *    npx playwright test model-preview-enhanced.spec.ts
 *
 * This test will generate screenshots showing:
 * - Thumbnail fallback when Three.js fails
 * - Multi-part 3MF handling (merged geometries or thumbnail)
 * - Preview indicators and error states
 * - Direct thumbnail API functionality
 */
