// Plate processing logic for 3MF files

import JSZip from 'jszip';
import type { ParsedPlateData, PlateObject } from '../../types/3mf';
import {
  parseProjectSettings,
  parseModelSettings,
  parseSliceInfo,
  extractFilamentColors,
} from './config';
import { parse3mfModel, extractObjects, findObjectById } from './parser';
import { extractVertices, extractIndices, extractPaintData } from './geometry';
import { extractTextureResources, processPaintedTriangles } from './texture';
import { parseTransformMatrix } from '../../utils/3d-math';
import { loadComponentMesh } from './components';

/**
 * Extract thumbnail for a specific plate
 */
export async function extractPlateThumbnail(
  zipContents: JSZip,
  plateIndex: number
): Promise<string | undefined> {
  const thumbnailPath = `Metadata/plate_${plateIndex + 1}.png`;
  const thumbnailFile = zipContents.file(thumbnailPath);

  if (thumbnailFile) {
    try {
      const thumbnailBlob = await thumbnailFile.async('blob');
      return URL.createObjectURL(thumbnailBlob);
    } catch (error) {
      console.warn(
        `Failed to extract thumbnail for plate ${plateIndex}:`,
        error
      );
    }
  }

  return undefined;
}

/**
 * Process a single plate from the 3MF file
 */
export async function processPlate(
  zipContents: JSZip,
  plateIndex: number
): Promise<ParsedPlateData> {
  // Load configuration files
  const projectSettingsFile = zipContents.file(
    'Metadata/project_settings.config'
  );
  const modelSettingsFile = zipContents.file('Metadata/model_settings.config');
  const sliceInfoFile = zipContents.file('Metadata/slice_info.config');

  let plates: Array<{ name: string; filaments: string[] }> = [];
  let filamentColors: Record<number, string> = {};

  if (projectSettingsFile) {
    const content = await projectSettingsFile.async('text');
    plates = parseProjectSettings(content);
  }

  if (modelSettingsFile || sliceInfoFile) {
    const modelSettings = modelSettingsFile
      ? parseModelSettings(await modelSettingsFile.async('text'))
      : {};
    const sliceInfo = sliceInfoFile
      ? parseSliceInfo(await sliceInfoFile.async('text'))
      : {};

    filamentColors = extractFilamentColors(modelSettings, sliceInfo);
  }

  // Load the main model file
  const modelFile = zipContents.file(/3D\/.*\.model$/i)?.[0];
  if (!modelFile) {
    throw new Error('No model file found in 3MF');
  }

  const modelXml = await modelFile.async('text');
  const model = parse3mfModel(modelXml);
  const objects = extractObjects(model);

  // Extract texture resources for painted models
  const textureResources = await extractTextureResources(modelXml, zipContents);

  // Process build items
  const plateObjects: PlateObject[] = [];
  const buildItems = model.model?.build?.item;

  if (buildItems) {
    const itemArray = Array.isArray(buildItems) ? buildItems : [buildItems];

    for (const item of itemArray) {
      const object = findObjectById(objects, item['@_objectid']);
      if (!object) continue;

      const transform = item['@_transform']
        ? parseTransformMatrix(item['@_transform'])
        : new Float32Array(16);

      // Process based on object type
      if (object['@_type'] === 'model' && object.mesh) {
        // Regular mesh object
        const vertices = extractVertices(object.mesh);
        const indices = extractIndices(object.mesh);

        if (vertices && indices) {
          const plateObject: PlateObject = {
            id: object['@_id'],
            type: 'normal',
            vertices,
            indices,
            transform,
            filamentColors,
          };

          // Check for painted triangles
          const paintData = extractPaintData(object.mesh);
          if (paintData.triangles && paintData.triangles.length > 0) {
            plateObject.type = 'painted';

            // Process painted triangles
            const paintedTriangleMap = processPaintedTriangles(
              paintData.triangles,
              textureResources
            );

            if (paintedTriangleMap.size > 0) {
              plateObject.paintedTriangles = Array.from(
                paintedTriangleMap.entries()
              ).map(([filamentIndex, triangleIndices]) => ({
                indices: new Uint32Array(
                  triangleIndices.flatMap(i => [
                    indices[i * 3],
                    indices[i * 3 + 1],
                    indices[i * 3 + 2],
                  ])
                ),
                filamentIndex,
              }));
            }
          }

          plateObjects.push(plateObject);
        }
      } else if (object.components?.component) {
        // Component-based object
        const componentResult = await loadComponentMesh(
          object,
          item,
          objects,
          zipContents,
          filamentColors
        );

        if (componentResult) {
          plateObjects.push(...componentResult);
        }
      }
    }
  }

  // Extract thumbnail
  const thumbnail = await extractPlateThumbnail(zipContents, plateIndex);

  // Get plate info
  const plateInfo = plates[plateIndex] || {
    name: `Plate ${plateIndex + 1}`,
    filaments: [],
  };

  return {
    index: plateIndex,
    name: plateInfo.name,
    filaments: plateInfo.filaments,
    objects: plateObjects,
    thumbnail,
    displayName: plateInfo.name || `Plate ${plateIndex + 1}`,
    objectCount: plateObjects.length,
  };
}
