// Texture processing for painted 3MF models

import JSZip from 'jszip';
import { XMLParser } from 'fast-xml-parser';
import type {
  ResourceTexture2D,
  ColorGroup3MF,
  Texture2DGroup3MF,
  TextureData,
  Triangle3MF,
} from '../../types/3mf';
import { decodeHexTexture } from './geometry';

const xmlParserOptions = {
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  textNodeName: '#text',
  parseAttributeValue: true,
  trimValues: true,
  processEntities: true,
  allowBooleanAttributes: true,
};

interface TextureResources {
  textures: Map<string, ResourceTexture2D>;
  colorGroups: Map<string, ColorGroup3MF>;
  texture2DGroups: Map<string, Texture2DGroup3MF>;
  textureData: Map<string, TextureData>;
}

/**
 * Extract texture resources from the model
 */
export async function extractTextureResources(
  modelXml: string,
  zipContents: JSZip
): Promise<TextureResources> {
  const parser = new XMLParser(xmlParserOptions);
  const parsed = parser.parse(modelXml);

  const resources: TextureResources = {
    textures: new Map(),
    colorGroups: new Map(),
    texture2DGroups: new Map(),
    textureData: new Map(),
  };

  const model = parsed.model;
  if (!model?.resources) {
    return resources;
  }

  // Extract texture2d resources
  if (model.resources.texture2d) {
    const textureArray = Array.isArray(model.resources.texture2d)
      ? model.resources.texture2d
      : [model.resources.texture2d];

    for (const texture of textureArray) {
      resources.textures.set(texture['@_id'], texture);

      // Try to load the actual texture data
      const texturePath = texture['@_path'];
      if (texturePath) {
        const textureFile = zipContents.file(texturePath);
        if (textureFile) {
          try {
            const content = await textureFile.async('text');
            const decoded = decodeHexTexture(content);
            if (decoded) {
              resources.textureData.set(texture['@_id'], decoded);
            }
          } catch (error) {
            console.warn(`Failed to load texture ${texturePath}:`, error);
          }
        }
      }
    }
  }

  // Extract colorgroup resources
  if (model.resources.colorgroup) {
    const colorGroupArray = Array.isArray(model.resources.colorgroup)
      ? model.resources.colorgroup
      : [model.resources.colorgroup];

    for (const colorGroup of colorGroupArray) {
      resources.colorGroups.set(colorGroup['@_id'], colorGroup);
    }
  }

  // Extract texture2dgroup resources
  if (model.resources.texture2dgroup) {
    const texture2DGroupArray = Array.isArray(model.resources.texture2dgroup)
      ? model.resources.texture2dgroup
      : [model.resources.texture2dgroup];

    for (const texture2DGroup of texture2DGroupArray) {
      resources.texture2DGroups.set(texture2DGroup['@_id'], texture2DGroup);
    }
  }

  return resources;
}

/**
 * Get UV coordinates for a triangle from texture2dgroup
 */
export function getTriangleUVs(
  triangle: Triangle3MF,
  texture2DGroup: Texture2DGroup3MF
): Array<{ u: number; v: number }> | null {
  if (!texture2DGroup.texcoord) {
    return null;
  }

  const texCoords = Array.isArray(texture2DGroup.texcoord)
    ? texture2DGroup.texcoord
    : [texture2DGroup.texcoord];

  // Get UV indices from triangle paint properties
  const tv1 = triangle['@_p1'];
  const tv2 = triangle['@_p2'];
  const tv3 = triangle['@_p3'];

  if (tv1 === undefined || tv2 === undefined || tv3 === undefined) {
    return null;
  }

  // Get the actual UV coordinates
  const uv1 = texCoords[tv1];
  const uv2 = texCoords[tv2];
  const uv3 = texCoords[tv3];

  if (!uv1 || !uv2 || !uv3) {
    return null;
  }

  return [
    { u: uv1['@_u'], v: uv1['@_v'] },
    { u: uv2['@_u'], v: uv2['@_v'] },
    { u: uv3['@_u'], v: uv3['@_v'] },
  ];
}

/**
 * Process painted triangles using texture data
 */
export function processPaintedTriangles(
  triangles: Triangle3MF[],
  textureResources: TextureResources
): Map<number, number[]> {
  const paintedTriangleMap = new Map<number, number[]>();

  triangles.forEach((triangle, index) => {
    const pid = triangle['@_pid'];
    if (pid === undefined) {
      return;
    }

    // Get the texture2dgroup
    const texture2DGroup = textureResources.texture2DGroups.get(String(pid));
    if (!texture2DGroup) {
      return;
    }

    // Get the texture data
    const textureData = textureResources.textureData.get(
      texture2DGroup['@_texid']
    );
    if (!textureData) {
      return;
    }

    // Get UV coordinates
    const uvs = getTriangleUVs(triangle, texture2DGroup);
    if (!uvs) {
      return;
    }

    // Sample the texture at the triangle's UV coordinates
    // For now, we'll use the primary filament index from the texture
    const filamentIndex = textureData.primaryFilamentIndex;

    if (!paintedTriangleMap.has(filamentIndex)) {
      paintedTriangleMap.set(filamentIndex, []);
    }
    paintedTriangleMap.get(filamentIndex)!.push(index);
  });

  return paintedTriangleMap;
}
