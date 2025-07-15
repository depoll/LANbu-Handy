// 3D math utilities for transformations and vector operations

import { Transform3MF } from '../types/3mf';

/**
 * Parse a transform string into a 4x4 matrix (column-major order for Three.js)
 */
export function parseTransformMatrix(
  transform: string | Transform3MF
): Float32Array {
  const matrix = new Float32Array(16);

  // Identity matrix
  matrix[0] = 1;
  matrix[4] = 0;
  matrix[8] = 0;
  matrix[12] = 0;
  matrix[1] = 0;
  matrix[5] = 1;
  matrix[9] = 0;
  matrix[13] = 0;
  matrix[2] = 0;
  matrix[6] = 0;
  matrix[10] = 1;
  matrix[14] = 0;
  matrix[3] = 0;
  matrix[7] = 0;
  matrix[11] = 0;
  matrix[15] = 1;

  if (typeof transform === 'string') {
    const values = transform.split(' ').map(parseFloat);
    if (values.length === 12) {
      // Row-major order in 3MF, convert to column-major for Three.js
      matrix[0] = values[0];
      matrix[4] = values[1];
      matrix[8] = values[2];
      matrix[12] = values[9];
      matrix[1] = values[3];
      matrix[5] = values[4];
      matrix[9] = values[5];
      matrix[13] = values[10];
      matrix[2] = values[6];
      matrix[6] = values[7];
      matrix[10] = values[8];
      matrix[14] = values[11];
      matrix[3] = 0;
      matrix[7] = 0;
      matrix[11] = 0;
      matrix[15] = 1;
    }
  } else if (transform) {
    // Using Transform3MF object
    matrix[0] = transform['@_m00'] ?? 1;
    matrix[4] = transform['@_m01'] ?? 0;
    matrix[8] = transform['@_m02'] ?? 0;
    matrix[12] = transform['@_m30'] ?? 0;

    matrix[1] = transform['@_m10'] ?? 0;
    matrix[5] = transform['@_m11'] ?? 1;
    matrix[9] = transform['@_m12'] ?? 0;
    matrix[13] = transform['@_m31'] ?? 0;

    matrix[2] = transform['@_m20'] ?? 0;
    matrix[6] = transform['@_m21'] ?? 0;
    matrix[10] = transform['@_m22'] ?? 1;
    matrix[14] = transform['@_m32'] ?? 0;

    matrix[3] = 0;
    matrix[7] = 0;
    matrix[11] = 0;
    matrix[15] = 1;
  }

  return matrix;
}

/**
 * Multiply two 4x4 matrices (Float32Array)
 */
export function multiplyMatrices(
  a: Float32Array,
  b: Float32Array
): Float32Array {
  const result = new Float32Array(16);

  for (let i = 0; i < 4; i++) {
    for (let j = 0; j < 4; j++) {
      let sum = 0;
      for (let k = 0; k < 4; k++) {
        sum += a[i * 4 + k] * b[k * 4 + j];
      }
      result[i * 4 + j] = sum;
    }
  }

  return result;
}

/**
 * Convert hex color string to RGB object (0-1 range)
 */
export function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})/.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16) / 255,
        g: parseInt(result[2], 16) / 255,
        b: parseInt(result[3], 16) / 255,
      }
    : { r: 0, g: 0, b: 0 };
}

/**
 * Calculate barycentric coordinates for a point in a triangle
 */
export function getBarycentricCoordinates(
  point: { u: number; v: number },
  v1: { u: number; v: number },
  v2: { u: number; v: number },
  v3: { u: number; v: number }
): { u: number; v: number; w: number } {
  const denom = (v2.v - v3.v) * (v1.u - v3.u) + (v3.u - v2.u) * (v1.v - v3.v);

  if (Math.abs(denom) < 1e-10) {
    return { u: 1 / 3, v: 1 / 3, w: 1 / 3 };
  }

  const u =
    ((v2.v - v3.v) * (point.u - v3.u) + (v3.u - v2.u) * (point.v - v3.v)) /
    denom;
  const v =
    ((v3.v - v1.v) * (point.u - v3.u) + (v1.u - v3.u) * (point.v - v3.v)) /
    denom;
  const w = 1 - u - v;

  return { u, v, w };
}
