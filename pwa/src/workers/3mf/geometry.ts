// Geometry extraction from 3MF mesh data

import type {
  Mesh3MF,
  Vertex3MF,
  Triangle3MF,
  TriangleColor3MF,
  TextureData,
  TriangleRegion,
  TriangleSubdivision,
} from '../../types/3mf';

/**
 * Extract vertices from parsed mesh
 */
export function extractVertices(mesh: Mesh3MF): Float32Array | null {
  if (!mesh.vertices?.vertex) {
    return null;
  }

  const vertexData = mesh.vertices.vertex;
  const vertexArray = Array.isArray(vertexData) ? vertexData : [vertexData];

  const vertices = new Float32Array(vertexArray.length * 3);

  vertexArray.forEach((vertex: Vertex3MF, index: number) => {
    vertices[index * 3] = vertex['@_x'] || 0;
    vertices[index * 3 + 1] = vertex['@_y'] || 0;
    vertices[index * 3 + 2] = vertex['@_z'] || 0;
  });

  return vertices;
}

/**
 * Extract indices from parsed mesh
 */
export function extractIndices(mesh: Mesh3MF): Uint32Array | null {
  if (!mesh.triangles?.triangle) {
    return null;
  }

  const triangleData = mesh.triangles.triangle;
  const triangleArray = Array.isArray(triangleData)
    ? triangleData
    : [triangleData];

  const indices = new Uint32Array(triangleArray.length * 3);

  triangleArray.forEach((triangle: Triangle3MF, index: number) => {
    indices[index * 3] = triangle['@_v1'];
    indices[index * 3 + 1] = triangle['@_v2'];
    indices[index * 3 + 2] = triangle['@_v3'];
  });

  return indices;
}

/**
 * Extract paint data from mesh
 */
export function extractPaintData(mesh: Mesh3MF): {
  triangleColors?: TriangleColor3MF[];
  triangles?: Triangle3MF[];
} {
  const result: {
    triangleColors?: TriangleColor3MF[];
    triangles?: Triangle3MF[];
  } = {};

  // Extract triangle colors if present
  if (mesh.trianglecolors?.color) {
    const colorData = mesh.trianglecolors.color;
    result.triangleColors = Array.isArray(colorData) ? colorData : [colorData];
  }

  // Extract triangles with paint data
  if (mesh.triangles?.triangle) {
    const triangleData = mesh.triangles.triangle;
    const triangleArray = Array.isArray(triangleData)
      ? triangleData
      : [triangleData];

    // Filter triangles that have paint properties
    const paintedTriangles = triangleArray.filter(
      t => t['@_pid'] !== undefined || t['@_p1'] !== undefined
    );

    if (paintedTriangles.length > 0) {
      result.triangles = paintedTriangles;
    }
  }

  return result;
}

/**
 * Decode hex-encoded texture data from Bambu Studio
 */
export function decodeHexTexture(hexData: string): TextureData | null {
  try {
    // Header: 4 bytes width, 4 bytes height
    const width = parseInt(hexData.substring(0, 8), 16);
    const height = parseInt(hexData.substring(8, 16), 16);

    // Data starts after header
    const dataHex = hexData.substring(16);

    // Decode the RLE data
    const filamentData: number[] = [];
    let i = 0;

    while (i < dataHex.length) {
      // Decode the count using variable-length encoding
      let count = 0;
      let bitPosition = 0;

      while (i < dataHex.length) {
        const nibble = parseInt(dataHex[i], 16);
        const dataBits = nibble & 0x7;

        // Add the data bits to the count at the current bit position
        count |= dataBits << bitPosition;
        bitPosition += 3;

        i++;

        // If continue bit is not set, we're done with this count
        if ((nibble & 0x8) === 0) {
          break;
        }
      }

      // The actual run length is count + 1
      const runLength = count + 1;

      // The next character is the color index
      if (i < dataHex.length) {
        const colorIndex = parseInt(dataHex[i], 16);
        i++;

        // Add 'runLength' entries with 'colorIndex'
        for (let j = 0; j < runLength; j++) {
          filamentData.push(colorIndex);
        }
      } else {
        console.warn(`Incomplete hex texture data at position ${i}`);
        break;
      }
    }

    // Find the most common non-zero filament index
    const filamentCounts = new Map<number, number>();
    filamentData.forEach(f => {
      if (f !== 0) {
        filamentCounts.set(f, (filamentCounts.get(f) || 0) + 1);
      }
    });

    let primaryFilamentIndex = 0;
    let maxCount = 0;
    filamentCounts.forEach((count, filament) => {
      if (count > maxCount) {
        maxCount = count;
        primaryFilamentIndex = filament;
      }
    });

    return { width, height, filamentData, primaryFilamentIndex };
  } catch (error) {
    console.error('Failed to decode hex texture:', error);
    return null;
  }
}

/**
 * Find regions of different colors in a triangle
 */
export function findTriangleRegions(
  triangleUVs: Array<{ u: number; v: number }>,
  textureData: TextureData,
  threshold: number = 0.02
): TriangleRegion[] {
  const regions: TriangleRegion[] = [];
  const width = textureData.width;
  const height = textureData.height;
  const filamentData = textureData.filamentData;

  // Group pixels by filament index
  const filamentPixels = new Map<number, Array<{ u: number; v: number }>>();

  // Sample the triangle area
  const sampleResolution = Math.max(50, Math.sqrt(width * height) / 10);

  for (let i = 0; i <= sampleResolution; i++) {
    for (let j = 0; j <= sampleResolution - i; j++) {
      const u = i / sampleResolution;
      const v = j / sampleResolution;
      const w = 1 - u - v;

      if (w >= 0) {
        // Interpolate UV coordinates
        const texU =
          u * triangleUVs[0].u + v * triangleUVs[1].u + w * triangleUVs[2].u;
        const texV =
          u * triangleUVs[0].v + v * triangleUVs[1].v + w * triangleUVs[2].v;

        // Convert to pixel coordinates
        const pixelX = Math.floor(texU * width);
        const pixelY = Math.floor(texV * height);

        if (pixelX >= 0 && pixelX < width && pixelY >= 0 && pixelY < height) {
          const pixelIndex = pixelY * width + pixelX;
          const filamentIndex = filamentData[pixelIndex];

          if (!filamentPixels.has(filamentIndex)) {
            filamentPixels.set(filamentIndex, []);
          }
          filamentPixels.get(filamentIndex)!.push({ u, v });
        }
      }
    }
  }

  // Convert pixel groups to regions
  filamentPixels.forEach((pixels, filamentIndex) => {
    if (
      pixels.length / ((sampleResolution * sampleResolution) / 2) >=
      threshold
    ) {
      // Find the convex hull or bounding polygon of the pixels
      // For simplicity, we'll use the centroid and approximate boundary
      const centroid = pixels.reduce(
        (acc, p) => ({ u: acc.u + p.u, v: acc.v + p.v }),
        { u: 0, v: 0 }
      );
      centroid.u /= pixels.length;
      centroid.v /= pixels.length;

      // Create a simplified boundary (could be improved with convex hull)
      const vertices: { u: number; v: number }[] = [];

      // Find extremal points
      const minU = Math.min(...pixels.map(p => p.u));
      const maxU = Math.max(...pixels.map(p => p.u));
      const minV = Math.min(...pixels.map(p => p.v));
      const maxV = Math.max(...pixels.map(p => p.v));

      // Create a simple bounding polygon
      vertices.push({ u: minU, v: minV });
      vertices.push({ u: maxU, v: minV });
      vertices.push({ u: maxU, v: maxV });
      vertices.push({ u: minU, v: maxV });

      regions.push({
        vertices,
        filament: filamentIndex,
        pixelCount: pixels.length,
      });
    }
  });

  return regions;
}

/**
 * Subdivide a triangle based on paint regions
 */
export function subdivideTriangleByRegions(
  triangle: Triangle3MF,
  regions: TriangleRegion[],
  vertices: Vertex3MF[],
  filamentData: { primaryFilamentIndex: number }
): TriangleSubdivision[] {
  if (regions.length === 0) {
    return [
      {
        triangle,
        filamentIndex: filamentData.primaryFilamentIndex,
      },
    ];
  }

  const subdivisions: TriangleSubdivision[] = [];
  const v1 = vertices[triangle['@_v1']];
  const v2 = vertices[triangle['@_v2']];
  const v3 = vertices[triangle['@_v3']];

  // For each region, create a subdivision
  regions.forEach(region => {
    // For simplicity, we'll create a fan from the centroid
    const centroid = region.vertices.reduce(
      (acc, v) => ({ u: acc.u + v.u, v: acc.v + v.v }),
      { u: 0, v: 0 }
    );
    centroid.u /= region.vertices.length;
    centroid.v /= region.vertices.length;

    // Convert barycentric to 3D
    const centerVertex: Vertex3MF = {
      '@_x':
        centroid.u * (v1['@_x'] || 0) +
        centroid.v * (v2['@_x'] || 0) +
        (1 - centroid.u - centroid.v) * (v3['@_x'] || 0),
      '@_y':
        centroid.u * (v1['@_y'] || 0) +
        centroid.v * (v2['@_y'] || 0) +
        (1 - centroid.u - centroid.v) * (v3['@_y'] || 0),
      '@_z':
        centroid.u * (v1['@_z'] || 0) +
        centroid.v * (v2['@_z'] || 0) +
        (1 - centroid.u - centroid.v) * (v3['@_z'] || 0),
    };

    subdivisions.push({
      triangle: triangle,
      filamentIndex: region.filament,
      newVertices: [centerVertex],
    });
  });

  return subdivisions;
}
