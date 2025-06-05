/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    typecheck: {
      tsconfig: './tsconfig.test.json',
    },
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/tests-playwright/**', // Exclude Playwright tests
      '**/*.spec.ts', // Exclude .spec.ts files (Playwright convention)
    ],
  },
});
