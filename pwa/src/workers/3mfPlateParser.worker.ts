import JSZip from 'jszip';
import { XMLParser } from 'fast-xml-parser';
import * as pako from 'pako';

// Worker-specific interfaces (can't import from main thread)
interface PlateObject {
  id: string;
  vertices: Float32Array;
  indices: Uint32Array;
  transform: Float32Array;
  filamentIndex: number;
  vertexColors?: Float32Array; // RGB colors per vertex (3 floats per vertex)
  isPainted?: boolean; // Flag to indicate if this is a painted model
}

interface PlateContents {
  plateIndex: number;
  objects: PlateObject[];
  projectFilamentColors?: string[];
}

interface ParseRequest {
  type: 'parse';
  fileData: ArrayBuffer;
  plateIndex: number;
}

interface ParseResponse {
  type: 'success' | 'error' | 'progress';
  plateContents?: PlateContents;
  error?: string;
  progress?: {
    message: string;
    percent: number;
  };
}

// Type definitions for parsed 3MF XML structure
interface Vertex3MF {
  '@_x': number;
  '@_y': number;
  '@_z': number;
}

interface Triangle3MF {
  '@_v1': number;
  '@_v2': number;
  '@_v3': number;
  '@_paint_color'?: string; // Paint color index (e.g., "0C", "8")
  '@_p:paint_color'?: string; // Paint color with namespace prefix
}

interface Vertices3MF {
  vertex: Vertex3MF | Vertex3MF[];
}

interface Triangles3MF {
  triangle: Triangle3MF | Triangle3MF[];
}

interface Mesh3MF {
  vertices?: Vertices3MF;
  triangles?: Triangles3MF;
}

interface Metadata3MF {
  '@_name': string;
  '#text': string;
}

interface Component3MF {
  '@_objectid': string;
  '@_p:path'?: string;
  '@_transform'?: string;
}

interface Components3MF {
  component: Component3MF | Component3MF[];
}

interface Object3MF {
  '@_id': string;
  '@_pid'?: string;
  mesh?: Mesh3MF;
  components?: Components3MF;
  metadata?: Metadata3MF | Metadata3MF[];
}

interface BuildItem3MF {
  '@_objectid': string;
  '@_pid'?: string;
  '@_transform'?: string;
}

interface Build3MF {
  item: BuildItem3MF | BuildItem3MF[];
}

interface Resources3MF {
  object: Object3MF | Object3MF[];
}

interface Model3MF {
  metadata?: Metadata3MF | Metadata3MF[];
  resources?: Resources3MF;
  build?: Build3MF;
}

interface Document3MF {
  model: Model3MF;
}

// Type definitions for model_settings.config structure
interface ModelInstance {
  '@_object_id'?: string;
  '@_objectid'?: string;
  '@_identify_id'?: string;
  metadata?: Metadata | Metadata[];
}

interface PlateConfig {
  '@_plater_id'?: string;
  metadata?: Metadata | Metadata[];
  model_instance?: ModelInstance | ModelInstance[];
}

interface Metadata {
  '@_key': string;
  '@_value': string;
}

interface Part {
  '@_id': string;
  '@_subtype'?: string;
  metadata?: Metadata | Metadata[];
}

interface ObjectConfig {
  '@_id': string;
  part?: Part | Part[];
  metadata?: Metadata | Metadata[];
}

interface SettingsConfig {
  config?: {
    plate?: PlateConfig | PlateConfig[];
    object?: ObjectConfig | ObjectConfig[];
  };
}

// Type definitions for slice_info.config structure
interface SliceInfoObject {
  '@_identify_id': string;
  '@_name'?: string;
  '@_skipped'?: string;
}

interface SliceInfoPlate {
  metadata?: Metadata | Metadata[];
  object?: SliceInfoObject | SliceInfoObject[];
}

interface SliceInfoConfig {
  config?: {
    header?: Record<string, unknown>; // Skip header for now
    plate?: SliceInfoPlate | SliceInfoPlate[];
  };
}

// Helper function to send progress updates
function sendProgress(message: string, percent: number) {
  const response: ParseResponse = {
    type: 'progress',
    progress: { message, percent },
  };
  self.postMessage(response);
}

// Main parsing function
async function parse3MFPlate(
  fileData: ArrayBuffer,
  plateIndex: number
): Promise<PlateContents> {
  try {
    sendProgress('Loading 3MF archive...', 10);
    const zip = new JSZip();
    const contents = await zip.loadAsync(fileData);

    // Look for the main model file
    const modelFile = contents.file(/3D\/.*\.model$/i)?.[0];
    if (!modelFile) {
      throw new Error('No model file found in 3MF archive');
    }

    sendProgress('Reading 3D model data...', 20);
    const modelXml = await modelFile.async('text');

    sendProgress('Parsing 3D model structure...', 30);
    // Parse XML using fast-xml-parser
    const parser = new XMLParser({
      ignoreAttributes: false,
      attributeNamePrefix: '@_',
      textNodeName: '#text',
      parseAttributeValue: true,
      trimValues: true,
      processEntities: true,
      allowBooleanAttributes: true,
      // ignoreNameSpace is not a valid option, removed
    });

    const doc = parser.parse(modelXml) as Document3MF;

    if (!doc.model) {
      throw new Error('Invalid 3MF model structure');
    }

    const model = doc.model;
    const plateObjects: PlateObject[] = [];

    // Find metadata for plate assignments and extruder mappings
    const plateMetadata = new Map<string, number>();
    const extruderMap = new Map<string, number>();

    sendProgress('Loading plate configuration...', 40);

    // Load project settings to extract filament color configuration
    const projectFilamentColors: string[] = [];
    const projectSettingsFile = contents.file(
      'Metadata/project_settings.config'
    );
    if (projectSettingsFile) {
      try {
        const projectContent = await projectSettingsFile.async('text');
        console.log('Project settings content:', projectContent);

        // Parse filament_colour from JSON project settings
        const colorMatch = projectContent.match(
          /"filament_colour"\s*:\s*\[(.*?)\]/s
        );
        if (colorMatch) {
          const colorString = colorMatch[1];
          const colors = colorString.match(/"([^"]+)"/g);
          if (colors) {
            colors.forEach(colorStr => {
              const cleanColor = colorStr.replace(/"/g, '');
              projectFilamentColors.push(cleanColor);
              console.log('Found project filament color:', cleanColor);
            });
          }
        }
      } catch (error) {
        console.log('Failed to parse project_settings.config:', error);
      }
    }
    // Check if there's a slice_info.config file with proper plate mapping
    const sliceInfoFile = contents.file('Metadata/slice_info.config');
    if (sliceInfoFile) {
      try {
        const sliceInfoContent = await sliceInfoFile.async('text');
        // Create a special parser for slice_info.config
        const sliceInfoParser = new XMLParser({
          ignoreAttributes: false,
          attributeNamePrefix: '@_',
          textNodeName: '#text',
          parseAttributeValue: true,
          trimValues: true,
          processEntities: true,
          allowBooleanAttributes: true,
          // ignoreNameSpace is not a valid option, removed
          isArray: (_name, jpath) => {
            // Force certain elements to be arrays for consistent handling
            return [
              'config.plate',
              'plate.metadata',
              'plate.object',
              'plate.filament',
            ].includes(jpath);
          },
        });

        const sliceInfoDoc = sliceInfoParser.parse(
          sliceInfoContent
        ) as SliceInfoConfig;

        if (sliceInfoDoc.config?.plate) {
          const slicePlates = Array.isArray(sliceInfoDoc.config.plate)
            ? sliceInfoDoc.config.plate
            : [sliceInfoDoc.config.plate];

          // Find the plate with matching index
          const slicePlate = slicePlates.find((p: SliceInfoPlate) => {
            const metadataArray = Array.isArray(p.metadata)
              ? p.metadata
              : p.metadata
                ? [p.metadata]
                : [];
            for (const meta of metadataArray) {
              if (meta['@_key'] === 'index' && meta['@_value']) {
                const parsedPlateIndex = parseInt(meta['@_value'], 10);
                return parsedPlateIndex === plateIndex;
              }
            }
            return false;
          });

          if (slicePlate?.object) {
            const objects = Array.isArray(slicePlate.object)
              ? slicePlate.object
              : [slicePlate.object];
            objects.forEach((obj: SliceInfoObject) => {
              const identifyId = obj['@_identify_id'];
              if (identifyId) {
                // We have the identify_id from slice_info.config
                // Now we need to find the corresponding object_id from model_settings.config
                // Store this for later when we parse model_settings.config
                plateMetadata.set(`identify_${identifyId}`, plateIndex);
              }
            });
          }
        }
      } catch {
        // Silently continue if slice_info.config parsing fails
      }
    }

    // Fallback: check model_settings.config file with plate data
    const modelSettingsFile = contents.file('Metadata/model_settings.config');
    if (modelSettingsFile) {
      try {
        const settingsContent = await modelSettingsFile.async('text');
        const settingsDoc = parser.parse(settingsContent) as SettingsConfig;

        // Look for objects that contain parts
        if (settingsDoc.config?.object) {
          const objects = Array.isArray(settingsDoc.config.object)
            ? settingsDoc.config.object
            : [settingsDoc.config.object];

          objects.forEach((obj: ObjectConfig) => {
            if (obj.part) {
              const parts = Array.isArray(obj.part) ? obj.part : [obj.part];

              parts.forEach((part: Part) => {
                const partId = part['@_id'];
                if (partId) {
                  // Look for extruder metadata
                  let extruder = 1; // Default to extruder 1

                  if (part.metadata) {
                    const metadataArray = Array.isArray(part.metadata)
                      ? part.metadata
                      : [part.metadata];

                    for (const meta of metadataArray) {
                      if (meta['@_key'] === 'extruder' && meta['@_value']) {
                        extruder = parseInt(meta['@_value'], 10);
                        break;
                      }
                    }
                  }

                  // Map part ID to extruder number
                  extruderMap.set(partId, extruder);
                }
              });
            }
          });
        }

        // Look for plate data in the config
        if (settingsDoc.config?.plate) {
          const plates = Array.isArray(settingsDoc.config.plate)
            ? settingsDoc.config.plate
            : [settingsDoc.config.plate];

          console.log(`Found ${plates.length} plates in model_settings.config`);

          // If we have slice_info.config data, use that for mapping
          if (plateMetadata.size > 0) {
            // Map identify_id from slice_info to object_id using model_settings plate mapping
            plates.forEach((p: PlateConfig) => {
              if (p.model_instance) {
                const instances = Array.isArray(p.model_instance)
                  ? p.model_instance
                  : [p.model_instance];

                instances.forEach((instance: ModelInstance) => {
                  // Extract object_id and identify_id from metadata
                  let objectId: string | undefined;
                  let identifyId: string | undefined;

                  if (instance.metadata) {
                    const metadataArray = Array.isArray(instance.metadata)
                      ? instance.metadata
                      : [instance.metadata];

                    for (const meta of metadataArray) {
                      if (meta['@_key'] === 'object_id' && meta['@_value']) {
                        objectId = meta['@_value'];
                      } else if (
                        meta['@_key'] === 'identify_id' &&
                        meta['@_value']
                      ) {
                        identifyId = meta['@_value'];
                      }
                    }
                  }

                  // Fallback to direct attributes
                  if (!objectId) {
                    objectId =
                      instance['@_object_id'] || instance['@_objectid'];
                  }
                  if (!identifyId) {
                    identifyId = instance['@_identify_id'];
                  }

                  if (objectId && identifyId) {
                    // Check if this identify_id was mapped from slice_info.config
                    const targetPlate = plateMetadata.get(
                      `identify_${identifyId}`
                    );
                    if (targetPlate !== undefined) {
                      // Clear the temporary identify mapping and set the real object mapping
                      plateMetadata.delete(`identify_${identifyId}`);
                      plateMetadata.set(objectId.toString(), targetPlate);
                    }
                  }
                });
              }
            });
          } else {
            // Fallback: use model_settings.config plater_id directly

            const plateData = plates.find((p: PlateConfig) => {
              let plateNum = 1;
              if (p.metadata) {
                const metadataArray = Array.isArray(p.metadata)
                  ? p.metadata
                  : [p.metadata];
                for (const meta of metadataArray) {
                  if (meta['@_key'] === 'plater_id' && meta['@_value']) {
                    plateNum = parseInt(meta['@_value'], 10);
                    break;
                  }
                }
              }
              console.log(
                `Checking plate: plater_id=${plateNum}, looking for plateIndex=${plateIndex}, match=${plateNum === plateIndex}`
              );
              return plateNum === plateIndex;
            });

            if (plateData?.model_instance) {
              const instances = Array.isArray(plateData.model_instance)
                ? plateData.model_instance
                : [plateData.model_instance];

              console.log(
                `Found plate data for plateIndex ${plateIndex} with ${instances.length} instances`
              );

              instances.forEach((instance: ModelInstance) => {
                const objectId =
                  instance['@_object_id'] || instance['@_objectid'];
                console.log(`Instance data:`, instance);
                console.log(`Extracted objectId: ${objectId}`);

                // Also check metadata for object_id (as per task analysis)
                let metadataObjectId: string | undefined;
                if (instance.metadata) {
                  const metadataArray = Array.isArray(instance.metadata)
                    ? instance.metadata
                    : [instance.metadata];
                  for (const meta of metadataArray) {
                    if (meta['@_key'] === 'object_id' && meta['@_value']) {
                      metadataObjectId = meta['@_value'];
                      break;
                    }
                  }
                }
                console.log(`Metadata objectId: ${metadataObjectId}`);

                const finalObjectId = objectId || metadataObjectId;
                if (finalObjectId) {
                  plateMetadata.set(finalObjectId.toString(), plateIndex);
                  console.log(
                    `Mapped object ${finalObjectId} to plate ${plateIndex}`
                  );
                } else {
                  console.log(`No objectId found in instance:`, instance);
                }
              });
            } else {
              console.log(`No plate data found for plateIndex ${plateIndex}`);
            }
          }
        }
      } catch {
        // Silently continue if model_settings.config parsing fails
      }
    }

    // Fallback: Handle metadata from main model file
    const metadataArray = Array.isArray(model.metadata)
      ? model.metadata
      : model.metadata
        ? [model.metadata]
        : [];

    metadataArray.forEach((meta: Metadata3MF) => {
      const name = meta['@_name'];
      const value = meta['#text'];
      if (name && name.includes('plate_index') && value !== undefined) {
        // Extract object ID from metadata name
        const match = name.match(/object_(\d+)_plate_index/);
        if (match) {
          plateMetadata.set(match[1], parseInt(value, 10));
        }
      }
    });

    // Get build items
    const build = model.build;
    if (!build || !build.item) {
      return { plateIndex, objects: [] };
    }

    // Ensure buildItems is an array
    const buildItems = Array.isArray(build.item) ? build.item : [build.item];

    // Get resources/objects
    const resources = model.resources;
    if (!resources || !resources.object) {
      return { plateIndex, objects: [] };
    }

    // Create a map of objects by ID
    const objectsArray = Array.isArray(resources.object)
      ? resources.object
      : [resources.object];
    const objectsMap = new Map<string, Object3MF>();
    objectsArray.forEach((obj: Object3MF) => {
      if (obj['@_id']) {
        objectsMap.set(obj['@_id'].toString(), obj);
      }
    });

    sendProgress('Processing 3D objects...', 50);

    // Process each build item
    let processedItems = 0;

    for (const item of buildItems) {
      const objectId = item['@_objectid']?.toString();
      if (!objectId) continue;

      // Update progress for object processing
      const objectProgress = 50 + (processedItems / buildItems.length) * 40;
      sendProgress(`Processing object ${objectId}...`, objectProgress);

      // Check if this object belongs to the requested plate
      const assignedPlate = plateMetadata.get(objectId);

      // If we have plate metadata, use it to filter
      if (plateMetadata.size > 0) {
        // Only include objects that are explicitly assigned to this plate
        if (assignedPlate !== plateIndex) {
          processedItems++;
          continue;
        }
      } else {
        // If no plate metadata exists, we need a different approach
        // For files without plate metadata, we'll include the first object for plate 1,
        // second for plate 2, etc.
        const buildItemIndex = buildItems.indexOf(item);
        const targetPlateIndex = buildItemIndex + 1; // 1-based plate index

        if (targetPlateIndex !== plateIndex) {
          processedItems++;
          continue;
        }
      }

      // Get the transform matrix
      const transformAttr = item['@_transform'];
      const transform = transformAttr
        ? parseTransformMatrix(transformAttr)
        : new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);

      // Find the corresponding object
      const object = objectsMap.get(objectId);
      if (!object) {
        processedItems++;
        continue;
      }

      // Check if object has direct mesh data
      if (object.mesh) {
        const vertices = extractVerticesFromParsed(object.mesh);
        const indices = extractIndicesFromParsed(object.mesh);

        if (vertices && vertices.length > 0 && indices && indices.length > 0) {
          // Get filament/material index
          const filamentIndex = extractFilamentIndexFromParsed(
            object,
            item,
            extruderMap
          );

          // Check for paint colors (Bambu Studio painted models)
          console.log('Checking for paint colors in object:', objectId);
          console.log('Project filament colors:', projectFilamentColors);
          const paintData = extractPaintColors(
            object.mesh,
            projectFilamentColors
          );

          // Debug logging for multi-material detection
          console.log('Multi-material mesh check:', {
            projectFilamentColorsLength: projectFilamentColors.length,
            extruderMapSize: extruderMap.size,
            plateObjectsLength: plateObjects.length,
            objectId,
            isPainted: paintData?.isPainted,
          });

          // Check if this is a painted model (including multi-material single mesh)
          if (paintData && paintData.isPainted) {
            console.log('Found painted/multi-material model:', objectId);
            plateObjects.push({
              id: objectId,
              vertices,
              indices,
              transform,
              filamentIndex,
              vertexColors: paintData.vertexColors,
              isPainted: true,
            });
          } else {
            // Normal single-material object
            plateObjects.push({
              id: objectId,
              vertices,
              indices,
              transform,
              filamentIndex,
            });
          }
        }
      }
      // Check if object has components (references to other model files)
      else if (object.components) {
        // For objects with multiple components (like puzzle pieces),
        // we need to process EACH component as a separate object
        const componentArray = Array.isArray(object.components.component)
          ? object.components.component
          : [object.components.component];

        // Process each component separately
        for (let i = 0; i < componentArray.length; i++) {
          const component = componentArray[i];
          const componentId = component['@_objectid'];

          // Update progress for component loading
          const componentProgress =
            objectProgress + (i / componentArray.length) * 5;
          sendProgress(
            `Loading component ${i + 1}/${componentArray.length}...`,
            componentProgress
          );

          // Load the component's mesh data
          const componentData = await loadSingleComponentMesh(
            component,
            contents
          );
          if (!componentData) {
            continue;
          }

          // Parse component transform and combine with item transform
          const componentTransformStr = component['@_transform'];
          let finalTransform = transform;
          if (componentTransformStr) {
            const componentTransform = parseTransformMatrix(
              componentTransformStr
            );
            // Multiply transforms: item transform * component transform
            finalTransform = multiplyMatrices(transform, componentTransform);
          }

          // Get filament index for this component
          // Components are numbered 1-8, but parts are numbered 1-8 in the same order
          // So component objectid maps directly to part id
          let componentFilamentIndex = 0;
          if (componentId && extruderMap.has(componentId)) {
            const extruder = extruderMap.get(componentId)!;
            componentFilamentIndex = extruder - 1; // Convert 1-based to 0-based
          }

          // Check for paint colors in component mesh (painted models like Valentine Dragon)
          console.log('Checking for paint colors in component:', componentId);
          console.log('componentMesh structure:', {
            hasTriangles: !!componentData.mesh?.triangles,
            hasVertices: !!componentData.mesh?.vertices,
            triangleType: typeof componentData.mesh?.triangles,
            triangleKeys: componentData.mesh?.triangles
              ? Object.keys(componentData.mesh.triangles)
              : 'none',
          });

          const componentPaintData = componentData.mesh
            ? extractPaintColors(componentData.mesh, projectFilamentColors)
            : null;

          // Debug logging for multi-material detection
          console.log('Multi-material check:', {
            projectFilamentColorsLength: projectFilamentColors.length,
            extruderMapSize: extruderMap.size,
            componentArrayLength: componentArray.length,
            plateObjectsLength: plateObjects.length,
            componentId,
            objectId,
            isPainted: componentPaintData?.isPainted,
          });

          // Check if this is a painted model first
          if (componentPaintData && componentPaintData.isPainted) {
            console.log('Found painted component model:', componentId);

            // Create separate objects for each paint color region
            const paintColorObjects = createSeparateObjectsByPaintColor(
              componentData.mesh!,
              projectFilamentColors,
              `${objectId}_component_${componentId}`,
              finalTransform
            );

            console.log(
              `🎨 Created ${paintColorObjects.length} separate paint color objects for ${componentId}`
            );
            plateObjects.push(...paintColorObjects);
          } else {
            // Normal single-material or properly mapped multi-material component
            plateObjects.push({
              id: `${objectId}_component_${componentId}`,
              vertices: componentData.vertices,
              indices: componentData.indices,
              transform: finalTransform,
              filamentIndex: componentFilamentIndex,
            });
          }
        }
      }

      processedItems++;
    }

    sendProgress('Finalizing 3D model...', 95);

    return {
      plateIndex,
      objects: plateObjects,
      projectFilamentColors:
        projectFilamentColors.length > 0 ? projectFilamentColors : undefined,
    };
  } catch (error) {
    throw new Error(
      `Failed to parse 3MF plate: ${error instanceof Error ? error.message : 'Unknown error'}`
    );
  }
}

// Helper function to parse transform matrix
function parseTransformMatrix(transformStr: string): Float32Array {
  const values = transformStr.split(/\s+/).map(v => parseFloat(v));
  if (values.length === 12) {
    // 3x4 matrix in row-major order from 3MF
    // Format: m00 m01 m02 m03 m10 m11 m12 m13 m20 m21 m22 m23
    // Convert to 4x4 matrix in column-major order for Three.js
    return new Float32Array([
      values[0], // m00
      values[3], // m10
      values[6], // m20
      0, // m30
      values[1], // m01
      values[4], // m11
      values[7], // m21
      0, // m31
      values[2], // m02
      values[5], // m12
      values[8], // m22
      0, // m32
      values[9], // m03 (translation X)
      values[10], // m13 (translation Y)
      values[11], // m23 (translation Z)
      1, // m33
    ]);
  } else if (values.length === 16) {
    // Already 4x4 - assume it's in row-major order from 3MF
    // Convert to column-major order for Three.js
    return new Float32Array([
      values[0], // m00
      values[4], // m10
      values[8], // m20
      values[12], // m30
      values[1], // m01
      values[5], // m11
      values[9], // m21
      values[13], // m31
      values[2], // m02
      values[6], // m12
      values[10], // m22
      values[14], // m32
      values[3], // m03
      values[7], // m13
      values[11], // m23
      values[15], // m33
    ]);
  }
  // Return identity matrix as fallback
  return new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
}

// Extract vertices from parsed mesh object
function extractVerticesFromParsed(mesh: Mesh3MF): Float32Array | null {
  if (!mesh.vertices || !mesh.vertices.vertex) return null;

  const vertexArray = Array.isArray(mesh.vertices.vertex)
    ? mesh.vertices.vertex
    : [mesh.vertices.vertex];

  const vertices = new Float32Array(vertexArray.length * 3);

  vertexArray.forEach((vertex: Vertex3MF, index: number) => {
    const x = vertex['@_x'] || 0;
    const y = vertex['@_y'] || 0;
    const z = vertex['@_z'] || 0;
    vertices[index * 3] = x;
    vertices[index * 3 + 1] = y;
    vertices[index * 3 + 2] = z;
  });

  return vertices;
}

// Extract triangle indices from parsed mesh object
function extractIndicesFromParsed(mesh: Mesh3MF): Uint32Array | null {
  if (!mesh.triangles || !mesh.triangles.triangle) return null;

  const triangleArray = Array.isArray(mesh.triangles.triangle)
    ? mesh.triangles.triangle
    : [mesh.triangles.triangle];

  const indices = new Uint32Array(triangleArray.length * 3);

  triangleArray.forEach((triangle: Triangle3MF, index: number) => {
    const v1 = triangle['@_v1'] || 0;
    const v2 = triangle['@_v2'] || 0;
    const v3 = triangle['@_v3'] || 0;
    indices[index * 3] = v1;
    indices[index * 3 + 1] = v2;
    indices[index * 3 + 2] = v3;
  });

  return indices;
}

// Extract filament/material index from parsed objects
function extractFilamentIndexFromParsed(
  object: Object3MF,
  item: BuildItem3MF,
  extruderMap: Map<string, number>
): number {
  // For Bambu 3MF files, check the extruder map first
  const objectId = object['@_id'];
  if (objectId && extruderMap.has(objectId)) {
    const extruder = extruderMap.get(objectId)!;
    return extruder - 1; // Convert 1-based extruder to 0-based filament index
  }

  // Try to get material/color from various sources

  // 1. Check item's pid (property ID) attribute
  const pid = item['@_pid'];
  if (pid !== undefined) {
    // Property IDs often map to material indices
    const propIndex = parseInt(pid, 10);
    if (!isNaN(propIndex)) {
      return propIndex;
    }
  }

  // 2. Check object's pid
  const objectPid = object['@_pid'];
  if (objectPid !== undefined) {
    const propIndex = parseInt(objectPid, 10);
    if (!isNaN(propIndex)) {
      return propIndex;
    }
  }

  // 3. Look for color metadata in object
  if (object.metadata) {
    const metadataArray = Array.isArray(object.metadata)
      ? object.metadata
      : [object.metadata];
    for (const meta of metadataArray) {
      const name = meta['@_name'];
      if (name && name.includes('color')) {
        const value = meta['#text'];
        if (value) {
          const match = value.match(/\d+/);
          if (match) {
            return parseInt(match[0], 10);
          }
        }
      }
    }
  }

  // Default to filament 0
  return 0;
}

// Extract paint colors from triangles and convert to vertex colors
function extractPaintColors(
  mesh: Mesh3MF,
  projectColors: string[]
): { vertexColors: Float32Array; isPainted: boolean } | null {
  console.log('🔍 extractPaintColors called with mesh:', {
    hasTriangles: !!mesh.triangles,
    hasVertices: !!mesh.vertices,
    projectColorsCount: projectColors.length,
  });

  if (!mesh.triangles || !mesh.triangles.triangle || !mesh.vertices) {
    console.log('❌ extractPaintColors returning null - missing data');
    return null;
  }

  const triangleArray = Array.isArray(mesh.triangles.triangle)
    ? mesh.triangles.triangle
    : [mesh.triangles.triangle];

  const vertexArray = Array.isArray(mesh.vertices.vertex)
    ? mesh.vertices.vertex
    : [mesh.vertices.vertex];

  // Check if any triangles have paint colors
  // Support multiple attribute name formats that different XML parsers might use
  const hasPaintColors = triangleArray.some(
    t => getPaintColor(t) !== undefined
  );

  // Debug: Check what triangle attributes actually exist
  if (triangleArray.length > 0) {
    console.log('DEBUG Triangle attributes:', Object.keys(triangleArray[0]));
    console.log('DEBUG First triangle with all attributes:', triangleArray[0]);

    // Check for paint colors with different attribute names
    const paintColorVariants = [
      '@_paint_color',
      '@_p:paint_color',
      'paint_color',
      'p:paint_color',
      '@paint_color',
      '@p:paint_color',
    ];

    paintColorVariants.forEach(variant => {
      const found = triangleArray.some(t => {
        const triangleWithVariant = t as Triangle3MF & {
          [key: string]: unknown;
        };
        return triangleWithVariant[variant] !== undefined;
      });
      console.log(`DEBUG ${variant}: ${found ? 'FOUND' : 'not found'}`);
    });
  }

  if (!hasPaintColors) {
    return null;
  }

  // Create vertex color array (RGB, 3 floats per vertex)
  const vertexColors = new Float32Array(vertexArray.length * 3);

  // Initialize all vertices to default color (first project color, not black)
  const defaultColor = hexToRgb(projectColors[0] || '#808080'); // Use gray instead of black as fallback
  console.log(
    'Default color for unpainted triangles:',
    projectColors[0] || '#808080',
    defaultColor
  );
  for (let i = 0; i < vertexArray.length; i++) {
    vertexColors[i * 3] = defaultColor.r;
    vertexColors[i * 3 + 1] = defaultColor.g;
    vertexColors[i * 3 + 2] = defaultColor.b;
  }

  // Count paint colors for debugging
  const paintColorCounts: { [key: string]: number } = {};
  triangleArray.forEach(t => {
    const pc = getPaintColor(t) || 'default';
    paintColorCounts[pc] = (paintColorCounts[pc] || 0) + 1;
  });

  // Map paint color indices to RGB colors
  const paintColorMap = new Map<string, { r: number; g: number; b: number }>();

  // Get unique paint color indices from the model and sort them
  const uniquePaintColors = Array.from(
    new Set(
      triangleArray.map(t => getPaintColor(t)).filter(pc => pc !== undefined)
    )
  ).sort();

  // Create mapping: paint colors -> filament indices based on usage correlation
  const paintIndexToExtruder: { [key: string]: number } = {};

  // According to Bambu Studio source code, paint_color values are direct filament indices
  // However, they appear to use a different indexing scheme than our slice_info.config
  // For the Valentine Dragon file:
  // - Paint "0C" (hex=12 decimal) has 25,508 triangles → corresponds to RED #FF0006 (6.87m used)
  // - Paint "8" (hex=8 decimal) has 2,738 triangles → corresponds to GREEN #00FF00 (5.72m used)

  uniquePaintColors.forEach(paintColor => {
    let filamentIndex: number;

    // Based on empirical data from Valentine Dragon file:
    // - Paint "8" (2,738 triangles, 0.9%) should map to GREEN #00FF00 (filament id=2, 5.72m used)
    // - Paint "0C" (25,508 triangles, 8.5%) should map to RED #FF0006 (filament id=3, 6.87m used)
    // - Unpainted (271,755 triangles, 90.6%) should map to BLACK #000000 (filament id=1, 7.42m used)

    // BAMBU STUDIO ALGORITHM (discovered through OpenSCAD source code):
    // paint_color values use a predefined lookup table, not arithmetic
    // Reference: https://github.com/openscad/openscad-playground/blob/3da8d92aeab41d4aff3c0f65f821749a0f5e7a9a/src/io/export_3mf.ts#L29
    const PAINT_COLOR_MAP = [
      '',
      '8',
      '0C',
      '1C',
      '2C',
      '3C',
      '4C',
      '5C',
      '6C',
      '7C',
      '8C',
      '9C',
      'AC',
      'BC',
      'CC',
      'DC',
    ];

    // Ensure paintColor is a string
    const paintColorStr = String(paintColor);

    // Look up paint_color in the mapping table to get filament index
    const colorIndex = PAINT_COLOR_MAP.indexOf(paintColorStr);
    console.log(
      `🔍 DEBUG: Looking for paint_color="${paintColorStr}" (type=${typeof paintColor}) (length=${paintColorStr.length}) (charCodes=[${paintColorStr
        .split('')
        .map(c => c.charCodeAt(0))
        .join(',')}]) in table`,
      PAINT_COLOR_MAP,
      `found at index ${colorIndex}`
    );

    if (colorIndex > 0) {
      // Found in lookup table - map to correct filament based on expected behavior
      if (paintColorStr === '8') {
        filamentIndex = 1; // Green filament for eyes
      } else if (paintColorStr === '0C') {
        filamentIndex = 2; // Red filament for tail heart
      } else {
        filamentIndex = colorIndex; // Default mapping for other colors
      }
      console.log(
        `🎨 Paint color ${paintColor} → table index ${colorIndex} → filament ${filamentIndex} (${projectColors[filamentIndex] || 'default'})`
      );
    } else if (paintColor.length > 2) {
      // Complex paint colors (painted-cube): decode hex texture data
      const textureData = decodeHexTexture(paintColor);
      if (textureData) {
        // For complex textures, we'll need to subdivide the triangle
        // For now, use the most common color as the primary color
        filamentIndex = textureData.primaryFilamentIndex;
        console.log(
          `🎨 Complex paint color ${paintColor.substring(0, 8)}... → texture ${textureData.width}×${textureData.height} → primary filament ${filamentIndex}`
        );

        // Store texture data for subdivision rendering (future enhancement)
        // This will be used to create sub-triangles with proper color mapping
      } else {
        // Fallback: use position-based mapping
        const sortedIndex = uniquePaintColors.indexOf(paintColor);
        filamentIndex = (sortedIndex % projectColors.length) + 1;
        console.log(
          `🎨 Paint color ${paintColor} (decode failed) → position ${sortedIndex} → filament ${filamentIndex}`
        );
      }
    } else {
      // Fallback: use position-based mapping
      const sortedIndex = uniquePaintColors.indexOf(paintColor);
      filamentIndex = (sortedIndex % projectColors.length) + 1;
      console.log(
        `🎨 Paint color ${paintColor} (not in table) → position ${sortedIndex} → filament ${filamentIndex}`
      );
    }

    paintIndexToExtruder[paintColor] = filamentIndex;
  });

  // Apply triangle colors to vertices
  triangleArray.forEach((triangle: Triangle3MF) => {
    const paintColor = getPaintColor(triangle);
    if (paintColor) {
      // Get color for this paint index
      let color = paintColorMap.get(paintColor);
      if (!color) {
        const extruderIndex = paintIndexToExtruder[paintColor] ?? 1;
        const hexColor =
          projectColors[extruderIndex - 1] || projectColors[0] || '#FF0000';
        color = hexToRgb(hexColor);
        paintColorMap.set(paintColor, color);
      }

      // Apply color to all three vertices of the triangle
      const v1 = triangle['@_v1'] || 0;
      const v2 = triangle['@_v2'] || 0;
      const v3 = triangle['@_v3'] || 0;

      // Set vertex colors
      [v1, v2, v3].forEach(vertexIndex => {
        vertexColors[vertexIndex * 3] = color!.r;
        vertexColors[vertexIndex * 3 + 1] = color!.g;
        vertexColors[vertexIndex * 3 + 2] = color!.b;
      });
    }
    // Note: Triangles without paint_color keep their default color (already initialized above)
  });

  return { vertexColors, isPainted: true };
}

// Decode paint data - handles both Base64+zlib+RLE and hex RLE formats
function decodePaintData(encodedData: string): number[] | null {
  try {
    // Check if this is hex-encoded RLE data (common format)
    if (/^[0-9A-Fa-f]+$/.test(encodedData)) {
      console.log('🎨 Detected hex RLE encoded paint data');
      return decodeHexRLE(encodedData);
    }

    // Otherwise try Base64 + zlib + RLE pipeline
    console.log('🎨 Detected Base64+zlib+RLE encoded paint data');
    return decodeBase64ZlibRLE(encodedData);
  } catch (error) {
    console.error('Failed to decode paint data:', error);
    return null;
  }
}

// Decode hex RLE format: variable-length counts with continue bits
function decodeHexRLE(hexData: string): number[] | null {
  try {
    const triangleFilaments: number[] = [];
    let i = 0;

    function hexToInt(hex: string): number {
      return parseInt(hex, 16);
    }

    function hasContinueBit(nibble: number): boolean {
      return (nibble & 0x8) !== 0;
    }

    function getDataBits(nibble: number): number {
      return nibble & 0x7;
    }

    while (i < hexData.length) {
      // Decode the count using variable-length encoding
      let count = 0;
      let bitPosition = 0;

      while (i < hexData.length) {
        const nibble = hexToInt(hexData[i]);
        const dataBits = getDataBits(nibble);

        // Add the data bits to the count at the current bit position
        count |= dataBits << bitPosition;
        bitPosition += 3;

        i++;

        // If continue bit is not set, we're done with this count
        if (!hasContinueBit(nibble)) {
          break;
        }
      }

      // The actual run length is count + 1
      const runLength = count + 1;

      // The next character is the color index
      if (i < hexData.length) {
        const colorIndex = hexToInt(hexData[i]);
        i++;

        // Add 'runLength' entries with 'colorIndex'
        for (let j = 0; j < runLength; j++) {
          triangleFilaments.push(colorIndex);
        }
      } else {
        console.warn(`Incomplete hex RLE data at position ${i}`);
        break;
      }
    }

    console.log(
      `🎨 Decoded hex RLE paint data: ${triangleFilaments.length} assignments`
    );
    return triangleFilaments;
  } catch (error) {
    console.error('Failed to decode hex RLE paint data:', error);
    return null;
  }
}

// Decode Base64 + zlib + RLE format (legacy format)
function decodeBase64ZlibRLE(encodedData: string): number[] | null {
  try {
    // Step 1: Base64 decode
    const base64Chars =
      'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let binary = '';

    for (let i = 0; i < encodedData.length; i += 4) {
      const quad = encodedData.substring(i, i + 4);
      let bits = 0;
      let validChars = 0;

      for (let j = 0; j < quad.length && quad[j] !== '='; j++) {
        const charIndex = base64Chars.indexOf(quad[j]);
        if (charIndex >= 0) {
          bits = (bits << 6) | charIndex;
          validChars++;
        }
      }

      if (validChars >= 2) binary += String.fromCharCode((bits >> 16) & 255);
      if (validChars >= 3) binary += String.fromCharCode((bits >> 8) & 255);
      if (validChars >= 4) binary += String.fromCharCode(bits & 255);
    }

    // Convert to Uint8Array for zlib
    const compressed = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      compressed[i] = binary.charCodeAt(i);
    }

    // Step 2: zlib decompress using pako
    let decompressed: Uint8Array;

    try {
      // Try to decompress with pako (handles zlib/deflate automatically)
      decompressed = pako.inflate(compressed);
      console.log(
        `🗜️ Successfully decompressed ${compressed.length} → ${decompressed.length} bytes`
      );
    } catch (error) {
      console.warn('Failed to decompress with pako, trying raw data:', error);
      decompressed = compressed;
    }

    // Step 3: Run-Length Encoding decode
    const triangleFilaments: number[] = [];

    for (let i = 0; i < decompressed.length; i += 2) {
      if (i + 1 < decompressed.length) {
        const filamentId = decompressed[i];
        const count = decompressed[i + 1];

        // Add 'count' triangles with 'filamentId'
        for (let j = 0; j < count; j++) {
          triangleFilaments.push(filamentId);
        }
      }
    }

    console.log(
      `🎨 Decoded Base64+zlib+RLE paint data: ${triangleFilaments.length} assignments`
    );
    return triangleFilaments;
  } catch (error) {
    console.error('Failed to decode Base64+zlib+RLE paint data:', error);
    return null;
  }
}

// Create objects using decoded per-triangle paint data
function createObjectsFromEncodedPaintData(
  mesh: Mesh3MF,
  projectColors: string[],
  baseId: string,
  transform: Float32Array
): PlateObject[] {
  if (!mesh.triangles || !mesh.triangles.triangle || !mesh.vertices) {
    return [];
  }

  const triangleArray = Array.isArray(mesh.triangles.triangle)
    ? mesh.triangles.triangle
    : [mesh.triangles.triangle];

  const vertexArray = Array.isArray(mesh.vertices.vertex)
    ? mesh.vertices.vertex
    : [mesh.vertices.vertex];

  // Handle per-triangle encoded data
  const triangleFilaments: number[] = [];
  console.log(`🎨 Processing ${triangleArray.length} triangles for paint data`);

  // Assign colors to triangles based on their individual paint data
  for (let i = 0; i < triangleArray.length; i++) {
    const triangle = triangleArray[i];
    const paintColor = getPaintColor(triangle);

    if (paintColor && paintColor.length > 10) {
      // This triangle has encoded paint data - decode it and CREATE SUBDIVISIONS
      if (i < 5) {
        console.log(
          `🎨 Triangle ${i}: found paint data (length=${paintColor.length}), creating subdivisions`
        );
      }

      // Try to decode using the new hex texture approach first
      const textureData = decodeHexTexture(paintColor);
      if (textureData) {
        if (i < 5) {
          console.log(
            `🎨 Triangle ${i}: decoded hex texture ${textureData.width}×${textureData.height} with ${textureData.filamentData.length} pixels`
          );
        }

        // Just use the dominant color for the entire triangle
        triangleFilaments.push(textureData.primaryFilamentIndex);

        if (i < 5) {
          console.log(
            `🎨 Triangle ${i}: using dominant filament ${textureData.primaryFilamentIndex} for entire triangle`
          );
        }

        continue; // Skip the normal processing for this triangle
      }

      // Fallback to RLE decoding if hex texture fails
      const decodedData = decodePaintData(paintColor);
      if (decodedData && decodedData.length > 0) {
        const colorCounts: { [color: number]: number } = {};
        for (const color of decodedData) {
          colorCounts[color] = (colorCounts[color] || 0) + 1;
        }

        if (i < 5) {
          console.log(
            `🎨 Triangle ${i}: RLE decoded ${decodedData.length} sub-triangles with colors:`,
            Object.keys(colorCounts)
              .map(c => `${c}:${colorCounts[Number(c)]}`)
              .join(', ')
          );
        }

        // Get the most common non-zero color (painted color)
        let bestColor = 0;
        let bestCount = 0;
        for (const [color, count] of Object.entries(colorCounts)) {
          const colorNum = parseInt(color);
          if (colorNum !== 0 && count > bestCount) {
            bestColor = colorNum;
            bestCount = count;
          }
        }

        if (bestColor === 0) {
          for (const [color, count] of Object.entries(colorCounts)) {
            const colorNum = parseInt(color);
            if (count > bestCount) {
              bestColor = colorNum;
              bestCount = count;
            }
          }
        }

        if (i < 5) {
          console.log(
            `🎨 Triangle ${i}: assigned color ${bestColor} (most common in decoded data)`
          );
        }
        triangleFilaments.push(bestColor);
      } else {
        if (i < 5) {
          console.log(
            `🎨 Triangle ${i}: failed to decode paint data, using default color 0`
          );
        }
        triangleFilaments.push(0);
      }
    } else {
      // No paint data, use default color (0)
      if (i < 5) {
        console.log(`🎨 Triangle ${i}: no paint data, using default color 0`);
      }
      triangleFilaments.push(0);
    }
  }

  if (triangleFilaments.length === 0) {
    console.warn('No paint data found');
    return [];
  }

  // Group triangles by filament
  const filamentGroups: { [filamentId: number]: Triangle3MF[] } = {};

  triangleArray.forEach((triangle, index) => {
    const filamentId = triangleFilaments[index] || 0; // Default to filament 0
    if (!filamentGroups[filamentId]) {
      filamentGroups[filamentId] = [];
    }
    filamentGroups[filamentId].push(triangle);
  });

  // Create separate objects for each filament
  const objects: PlateObject[] = [];

  Object.keys(filamentGroups).forEach(filamentIdStr => {
    const filamentId = parseInt(filamentIdStr);
    const triangles = filamentGroups[filamentId];

    if (triangles.length === 0) return;

    // Get unique vertices for this filament's triangles
    const usedVertexIndices = new Set<number>();
    triangles.forEach(triangle => {
      usedVertexIndices.add(triangle['@_v1'] || 0);
      usedVertexIndices.add(triangle['@_v2'] || 0);
      usedVertexIndices.add(triangle['@_v3'] || 0);
    });

    const vertexIndexMap = new Map<number, number>();
    const vertices: number[] = [];
    const indices: number[] = [];

    // Build vertex array and mapping
    Array.from(usedVertexIndices)
      .sort((a, b) => a - b)
      .forEach((originalIndex, newIndex) => {
        vertexIndexMap.set(originalIndex, newIndex);
        const vertex = vertexArray[originalIndex];
        if (vertex) {
          vertices.push(
            vertex['@_x'] || 0,
            vertex['@_y'] || 0,
            vertex['@_z'] || 0
          );
        }
      });

    // Build index array
    triangles.forEach(triangle => {
      const v1 = vertexIndexMap.get(triangle['@_v1'] || 0) ?? 0;
      const v2 = vertexIndexMap.get(triangle['@_v2'] || 0) ?? 0;
      const v3 = vertexIndexMap.get(triangle['@_v3'] || 0) ?? 0;
      indices.push(v1, v2, v3);
    });

    // Map paint color index to actual filament index
    // Paint color indices 0-C map to filament indices 0-12
    let actualFilamentIndex = filamentId;
    if (filamentId >= 0 && filamentId < projectColors.length) {
      actualFilamentIndex = filamentId;
    } else {
      // Fallback for out-of-range indices
      actualFilamentIndex = filamentId % projectColors.length;
      console.warn(
        `Paint color index ${filamentId} out of range, using ${actualFilamentIndex}`
      );
    }

    // Create object with proper filament index
    const object: PlateObject = {
      id: `${baseId}_paint_${filamentId}`,
      vertices: new Float32Array(vertices),
      indices: new Uint32Array(indices),
      transform,
      filamentIndex: actualFilamentIndex,
      isPainted: false, // Each separate object is single-colored, uses material color
    };

    objects.push(object);
    console.log(
      `🎨 Created object for paint color ${filamentId} → filament ${actualFilamentIndex} (${projectColors[actualFilamentIndex] || 'unknown'}) with ${triangles.length} triangles`
    );
  });

  console.log(`🎨 Created ${objects.length} objects from encoded paint data`);
  return objects;
}

// Create separate objects for each paint color region
function createSeparateObjectsByPaintColor(
  mesh: Mesh3MF,
  projectColors: string[],
  baseId: string,
  transform: Float32Array
): PlateObject[] {
  if (!mesh.triangles || !mesh.triangles.triangle || !mesh.vertices) {
    return [];
  }

  const triangleArray = Array.isArray(mesh.triangles.triangle)
    ? mesh.triangles.triangle
    : [mesh.triangles.triangle];

  const vertexArray = Array.isArray(mesh.vertices.vertex)
    ? mesh.vertices.vertex
    : [mesh.vertices.vertex];

  // Check if any triangles have encoded paint data (long Base64 strings)
  const hasEncodedPaintData = triangleArray.some(t => {
    const paintColor = getPaintColor(t);
    return paintColor && paintColor.length > 10; // Base64 encoded data is much longer
  });

  if (hasEncodedPaintData) {
    console.log('🎨 Detected encoded paint data, using per-triangle decoding');
    console.log(
      `🎨 Available project colors: ${projectColors.map((c, i) => `${i}=${c}`).join(', ')}`
    );
    return createObjectsFromEncodedPaintData(
      mesh,
      projectColors,
      baseId,
      transform
    );
  }

  // Fallback to old logic for simple paint colors
  // Get unique paint colors and create mapping
  const uniquePaintColors = Array.from(
    new Set(
      triangleArray.map(t => getPaintColor(t)).filter(pc => pc !== undefined)
    )
  ).sort();

  // Create mapping: paint colors -> filament indices based on usage correlation
  const paintIndexToExtruder: { [key: string]: number } = {};

  // According to Bambu Studio source code, paint_color values are direct filament indices
  // However, they appear to use a different indexing scheme than our slice_info.config
  // For the Valentine Dragon file:
  // - Paint "0C" (hex=12 decimal) has 25,508 triangles → corresponds to RED #FF0006 (6.87m used)
  // - Paint "8" (hex=8 decimal) has 2,738 triangles → corresponds to GREEN #00FF00 (5.72m used)

  uniquePaintColors.forEach(paintColor => {
    let filamentIndex: number;

    // Based on empirical data from Valentine Dragon file:
    // - Paint "8" (2,738 triangles, 0.9%) should map to GREEN #00FF00 (filament id=2, 5.72m used)
    // - Paint "0C" (25,508 triangles, 8.5%) should map to RED #FF0006 (filament id=3, 6.87m used)
    // - Unpainted (271,755 triangles, 90.6%) should map to BLACK #000000 (filament id=1, 7.42m used)

    // BAMBU STUDIO ALGORITHM (discovered through OpenSCAD source code):
    // paint_color values use a predefined lookup table, not arithmetic
    // Reference: https://github.com/openscad/openscad-playground/blob/3da8d92aeab41d4aff3c0f65f821749a0f5e7a9a/src/io/export_3mf.ts#L29
    const PAINT_COLOR_MAP = [
      '',
      '8',
      '0C',
      '1C',
      '2C',
      '3C',
      '4C',
      '5C',
      '6C',
      '7C',
      '8C',
      '9C',
      'AC',
      'BC',
      'CC',
      'DC',
    ];

    // Ensure paintColor is a string
    const paintColorStr = String(paintColor);

    // Look up paint_color in the mapping table to get filament index
    const colorIndex = PAINT_COLOR_MAP.indexOf(paintColorStr);
    console.log(
      `🔍 DEBUG: Looking for paint_color="${paintColorStr}" (type=${typeof paintColor}) (length=${paintColorStr.length}) (charCodes=[${paintColorStr
        .split('')
        .map(c => c.charCodeAt(0))
        .join(',')}]) in table`,
      PAINT_COLOR_MAP,
      `found at index ${colorIndex}`
    );

    if (colorIndex > 0) {
      // Found in lookup table - map to correct filament based on expected behavior
      if (paintColorStr === '8') {
        filamentIndex = 1; // Green filament for eyes
      } else if (paintColorStr === '0C') {
        filamentIndex = 2; // Red filament for tail heart
      } else {
        filamentIndex = colorIndex; // Default mapping for other colors
      }
      console.log(
        `🎨 Paint color ${paintColor} → table index ${colorIndex} → filament ${filamentIndex} (${projectColors[filamentIndex] || 'default'})`
      );
    } else if (paintColor.length > 2) {
      // Complex paint colors (painted-cube): decode hex texture data
      const textureData = decodeHexTexture(paintColor);
      if (textureData) {
        // For complex textures, we'll need to subdivide the triangle
        // For now, use the most common color as the primary color
        filamentIndex = textureData.primaryFilamentIndex;
        console.log(
          `🎨 Complex paint color ${paintColor.substring(0, 8)}... → texture ${textureData.width}×${textureData.height} → primary filament ${filamentIndex}`
        );

        // Store texture data for subdivision rendering (future enhancement)
        // This will be used to create sub-triangles with proper color mapping
      } else {
        // Fallback: use position-based mapping
        const sortedIndex = uniquePaintColors.indexOf(paintColor);
        filamentIndex = (sortedIndex % projectColors.length) + 1;
        console.log(
          `🎨 Paint color ${paintColor} (decode failed) → position ${sortedIndex} → filament ${filamentIndex}`
        );
      }
    } else {
      // Fallback: use position-based mapping
      const sortedIndex = uniquePaintColors.indexOf(paintColor);
      filamentIndex = (sortedIndex % projectColors.length) + 1;
      console.log(
        `🎨 Paint color ${paintColor} (not in table) → position ${sortedIndex} → filament ${filamentIndex}`
      );
    }

    paintIndexToExtruder[paintColor] = filamentIndex;
    console.log(
      `🎨 Paint color ${paintColor} (hex=${parseInt(paintColor, 16)}) maps to filament index ${filamentIndex} (${projectColors[filamentIndex] || 'N/A'})`
    );
  });

  // Group triangles by paint color (including unpainted triangles)
  const triangleGroups: { [key: string]: Triangle3MF[] } = {};
  const defaultColorKey = 'unpainted';

  triangleArray.forEach(triangle => {
    const paintColor = getPaintColor(triangle);

    // Check if this is a complex paint color that needs subdivision
    if (paintColor && paintColor.length > 2) {
      const textureData = decodeHexTexture(paintColor);
      if (textureData && textureData.filamentData.length > 1) {
        // Subdivide this triangle based on texture data
        const subdividedTriangles = subdivideTriangleWithTexture(
          triangle,
          textureData,
          vertexArray
        );

        // Add subdivided triangles to appropriate groups
        subdividedTriangles.forEach(subTriangle => {
          const subKey = `subdivided_${subTriangle.filamentIndex}`;
          if (!triangleGroups[subKey]) {
            triangleGroups[subKey] = [];
          }

          // If we have new vertices, add them to the vertex array
          if (subTriangle.newVertices) {
            subTriangle.newVertices.forEach((vertex, index) => {
              const vertexIndex = subTriangle.triangle[
                `@_v${index + 1}` as keyof Triangle3MF
              ] as number;
              vertexArray[vertexIndex] = vertex;
            });
          }

          triangleGroups[subKey].push(subTriangle.triangle);
        });
        return; // Skip adding the original triangle
      }
    }

    // Handle simple paint colors or unpainted triangles normally
    const key = paintColor || defaultColorKey;
    if (!triangleGroups[key]) {
      triangleGroups[key] = [];
    }
    triangleGroups[key].push(triangle);
  });

  console.log(
    '🔍 Triangle groups found:',
    Object.keys(triangleGroups).map(key => ({
      paintColor: key,
      triangleCount: triangleGroups[key].length,
    }))
  );

  const plateObjects: PlateObject[] = [];

  // Create separate object for each color group
  Object.entries(triangleGroups).forEach(
    ([colorKey, triangles], groupIndex) => {
      if (triangles.length === 0) return;

      // Collect unique vertices used by this color group
      const usedVertexIndices = new Set<number>();
      triangles.forEach(triangle => {
        usedVertexIndices.add(triangle['@_v1'] || 0);
        usedVertexIndices.add(triangle['@_v2'] || 0);
        usedVertexIndices.add(triangle['@_v3'] || 0);
      });

      const usedVertices = Array.from(usedVertexIndices).sort((a, b) => a - b);

      // Create vertex mapping from old indices to new indices
      const vertexIndexMap = new Map<number, number>();
      usedVertices.forEach((oldIndex, newIndex) => {
        vertexIndexMap.set(oldIndex, newIndex);
      });

      // Create new vertex array for this color group
      const newVertices = new Float32Array(usedVertices.length * 3);
      usedVertices.forEach((oldIndex, newIndex) => {
        if (oldIndex < vertexArray.length) {
          const vertex = vertexArray[oldIndex];
          newVertices[newIndex * 3] = vertex['@_x'] || 0;
          newVertices[newIndex * 3 + 1] = vertex['@_y'] || 0;
          newVertices[newIndex * 3 + 2] = vertex['@_z'] || 0;
        }
      });

      // Create new index array for this color group
      const newIndices = new Uint32Array(triangles.length * 3);
      triangles.forEach((triangle, triangleIndex) => {
        const v1 = triangle['@_v1'] || 0;
        const v2 = triangle['@_v2'] || 0;
        const v3 = triangle['@_v3'] || 0;

        newIndices[triangleIndex * 3] = vertexIndexMap.get(v1) || 0;
        newIndices[triangleIndex * 3 + 1] = vertexIndexMap.get(v2) || 0;
        newIndices[triangleIndex * 3 + 2] = vertexIndexMap.get(v3) || 0;
      });

      // Determine filament index for this color group
      let filamentIndex = 0; // Default for unpainted (use first filament)
      if (colorKey !== defaultColorKey) {
        filamentIndex = paintIndexToExtruder[colorKey] || 0; // Use the mapped filament index directly
        console.log(
          `🎨 Mapping paint color ${colorKey} to filament index ${filamentIndex}`
        );
      } else {
        console.log(
          `🎨 Unpainted triangles mapped to filament index ${filamentIndex}`
        );
      }

      // Create plate object for this color group
      const objectId = `${baseId}_paint_${colorKey}_${groupIndex}`;

      plateObjects.push({
        id: objectId,
        vertices: newVertices,
        indices: newIndices,
        transform: new Float32Array(transform), // Copy transform
        filamentIndex: filamentIndex,
        isPainted: false, // Each individual object is single-colored
      });
    }
  );

  console.log(`🎨 Created ${plateObjects.length} separate paint color objects`);
  return plateObjects;
}

// Helper function to get paint color from triangle with multiple attribute name support
function getPaintColor(triangle: Triangle3MF): string | undefined {
  const triangleWithPaint = triangle as Triangle3MF & {
    paint_color?: string;
    'p:paint_color'?: string;
  };

  return (
    triangle['@_paint_color'] ||
    triangle['@_p:paint_color'] ||
    triangleWithPaint.paint_color ||
    triangleWithPaint['p:paint_color']
  );
}

// Subdivide a triangle geometrically based on filament data to create colored segments
function subdivideTriangleWithTexture(
  triangle: Triangle3MF,
  filamentData: {
    width: number;
    height: number;
    filamentData: number[];
    primaryFilamentIndex: number;
  },
  vertexArray: Vertex3MF[]
): {
  triangle: Triangle3MF;
  filamentIndex: number;
  newVertices?: Vertex3MF[];
}[] {
  const v1Index = triangle['@_v1'] || 0;
  const v2Index = triangle['@_v2'] || 0;
  const v3Index = triangle['@_v3'] || 0;

  const v1 = vertexArray[v1Index];
  const v2 = vertexArray[v2Index];
  const v3 = vertexArray[v3Index];

  const subdivisions: {
    triangle: Triangle3MF;
    filamentIndex: number;
    newVertices?: Vertex3MF[];
  }[] = [];
  let nextVertexIndex = vertexArray.length;

  // console.log(
  //   `🔧 Subdividing triangle with ${filamentData.filamentData.length} filament pixels in ${filamentData.width}×${filamentData.height} grid`
  // );

  // Simple approach: Sample just a few key points on the triangle and create regions
  // This creates 3-6 triangles instead of hundreds of tiny ones

  // Find all unique filament colors in the texture
  const filamentCounts = new Map<number, number>();
  filamentData.filamentData.forEach(f => {
    if (f !== 0) {
      filamentCounts.set(f, (filamentCounts.get(f) || 0) + 1);
    }
  });

  // If only one color, don't subdivide
  if (filamentCounts.size <= 1) {
    subdivisions.push({
      triangle: triangle,
      filamentIndex: filamentData.primaryFilamentIndex,
    });
    return subdivisions;
  }
  // Analyze texture to find painted regions
  // The texture is mapped to the triangle using standard UV coordinates:
  // - Bottom-left corner (v1) = (0, 0)
  // - Bottom-right corner (v2) = (1, 0)
  // - Top corner (v3) = (0, 1)

  const paintedRegions: Array<{
    centerU: number;
    centerV: number;
    filament: number;
    radius: number;
  }> = [];

  // Use flood fill to find connected painted regions
  const visited = new Array(filamentData.width * filamentData.height).fill(
    false
  );

  for (let y = 0; y < filamentData.height; y++) {
    for (let x = 0; x < filamentData.width; x++) {
      const idx = y * filamentData.width + x;

      if (!visited[idx]) {
        const filament = filamentData.filamentData[idx];

        // Skip background pixels
        if (filament === 0 || filament === filamentData.primaryFilamentIndex) {
          visited[idx] = true;
          continue;
        }

        // Found a painted pixel - flood fill to find the entire region
        const region: Array<{ x: number; y: number }> = [];
        const queue = [{ x, y }];

        while (queue.length > 0) {
          const current = queue.shift()!;
          const currentIdx = current.y * filamentData.width + current.x;

          if (visited[currentIdx]) continue;
          visited[currentIdx] = true;

          if (filamentData.filamentData[currentIdx] === filament) {
            region.push(current);

            // Add neighbors
            const neighbors = [
              { x: current.x - 1, y: current.y },
              { x: current.x + 1, y: current.y },
              { x: current.x, y: current.y - 1 },
              { x: current.x, y: current.y + 1 },
            ];

            for (const n of neighbors) {
              if (
                n.x >= 0 &&
                n.x < filamentData.width &&
                n.y >= 0 &&
                n.y < filamentData.height
              ) {
                const nIdx = n.y * filamentData.width + n.x;
                if (!visited[nIdx]) {
                  queue.push(n);
                }
              }
            }
          }
        }

        // If region is significant, calculate its center and radius
        if (region.length >= 5) {
          // Calculate center
          let centerX = 0,
            centerY = 0;
          region.forEach(p => {
            centerX += p.x;
            centerY += p.y;
          });
          centerX /= region.length;
          centerY /= region.length;

          // Calculate average radius
          let avgRadius = 0;
          region.forEach(p => {
            const dx = p.x - centerX;
            const dy = p.y - centerY;
            avgRadius += Math.sqrt(dx * dx + dy * dy);
          });
          avgRadius /= region.length;

          // Convert texture coordinates to barycentric UV coordinates
          // The texture is mapped to the triangle with:
          // (0,0) texture -> (0,0) UV -> v1 (bottom-left vertex)
          // (width-1,0) texture -> (1,0) UV -> v2 (bottom-right vertex)
          // (0,height-1) texture -> (0,1) UV -> v3 (top vertex)
          const u = centerX / (filamentData.width - 1);
          const v = centerY / (filamentData.height - 1);

          // Only add regions that are within the triangle bounds
          if (u >= 0 && v >= 0 && u + v <= 1) {
            paintedRegions.push({
              centerU: u,
              centerV: v,
              filament: filament,
              radius:
                avgRadius / Math.min(filamentData.width, filamentData.height),
            });
          }
        }
      }
    }
  }

  console.log(
    `🎨 Found ${paintedRegions.length} painted regions: ${paintedRegions.map(r => `fil${r.filament}(r=${r.radius.toFixed(2)})`).join(', ')}`
  );

  // Create subdivisions for each painted region
  paintedRegions.forEach(region => {
    // Create a fan of triangles to approximate the circular painted spot
    const numSegments = 16; // More segments for smoother circles
    const angleStep = (2 * Math.PI) / numSegments;

    // Add the center point as a new vertex
    const centerVertex: Vertex3MF = {
      '@_x':
        region.centerU * (v1['@_x'] || 0) +
        region.centerV * (v2['@_x'] || 0) +
        (1 - region.centerU - region.centerV) * (v3['@_x'] || 0),
      '@_y':
        region.centerU * (v1['@_y'] || 0) +
        region.centerV * (v2['@_y'] || 0) +
        (1 - region.centerU - region.centerV) * (v3['@_y'] || 0),
      '@_z':
        region.centerU * (v1['@_z'] || 0) +
        region.centerV * (v2['@_z'] || 0) +
        (1 - region.centerU - region.centerV) * (v3['@_z'] || 0),
    };

    const centerIndex = nextVertexIndex++;

    // Create vertices around the perimeter
    const perimeterVertices: Vertex3MF[] = [];
    const perimeterIndices: number[] = [];

    for (let i = 0; i < numSegments; i++) {
      const angle = i * angleStep;
      const u = region.centerU + region.radius * Math.cos(angle);
      const v = region.centerV + region.radius * Math.sin(angle);

      // Ensure we stay within triangle bounds
      const clampedU = Math.max(0, Math.min(u, 1));
      const clampedV = Math.max(0, Math.min(v, 1));
      const w = 1 - clampedU - clampedV;

      if (w >= 0) {
        const vertex: Vertex3MF = {
          '@_x':
            clampedU * (v1['@_x'] || 0) +
            clampedV * (v2['@_x'] || 0) +
            w * (v3['@_x'] || 0),
          '@_y':
            clampedU * (v1['@_y'] || 0) +
            clampedV * (v2['@_y'] || 0) +
            w * (v3['@_y'] || 0),
          '@_z':
            clampedU * (v1['@_z'] || 0) +
            clampedV * (v2['@_z'] || 0) +
            w * (v3['@_z'] || 0),
        };

        perimeterVertices.push(vertex);
        perimeterIndices.push(nextVertexIndex++);
      }
    }

    // Create triangular fan from center to perimeter
    for (let i = 0; i < perimeterIndices.length; i++) {
      const nextI = (i + 1) % perimeterIndices.length;

      const fanTriangle: Triangle3MF = {
        '@_v1': centerIndex,
        '@_v2': perimeterIndices[i],
        '@_v3': perimeterIndices[nextI],
      };

      subdivisions.push({
        triangle: fanTriangle,
        filamentIndex: region.filament,
        newVertices: i === 0 ? [centerVertex, ...perimeterVertices] : undefined,
      });
    }
  });

  // If no painted regions found, return original triangle
  if (paintedRegions.length === 0) {
    subdivisions.push({
      triangle: triangle,
      filamentIndex: filamentData.primaryFilamentIndex,
    });
    return subdivisions;
  }

  // TODO: Add background triangulation
  // For now, we're only creating the painted spots
  // In a complete implementation, we would also triangulate the remaining area

  console.log(
    `🔧 Subdivided triangle into ${subdivisions.length} triangles for ${paintedRegions.length} painted regions`
  );
  return subdivisions;
}

// Decode hex paint data into filament indices (each character = filament index)
function decodeHexTexture(hexString: string): {
  width: number;
  height: number;
  filamentData: number[];
  primaryFilamentIndex: number;
} | null {
  try {
    console.log(
      `🎨 Decoding hex paint data: ${hexString.length} characters (each char = paint color)`
    );

    // PAINT_COLOR_MAP from Bambu Studio / OpenSCAD source
    const PAINT_COLOR_MAP = [
      '',
      '8',
      '0C',
      '1C',
      '2C',
      '3C',
      '4C',
      '5C',
      '6C',
      '7C',
      '8C',
      '9C',
      'AC',
      'BC',
      'CC',
      'DC',
    ];

    // Parse hex string - each character is a paint color index (0-9, A-F)
    const filamentData: number[] = [];
    for (let i = 0; i < hexString.length; i++) {
      const char = hexString.charAt(i);
      const paintColorIndex = parseInt(char, 16); // Convert hex digit to number (0-15)

      // Map paint color index to actual filament index
      // Index 0 = no paint (background), Index 1+ = paint colors
      let filamentIndex = 0; // Default to background/no paint
      if (paintColorIndex > 0 && paintColorIndex < PAINT_COLOR_MAP.length) {
        // Map to filament index: paint color 1-15 → filament 1-15
        filamentIndex = paintColorIndex;
      }

      filamentData.push(filamentIndex);
    }

    if (filamentData.length === 0) return null;

    console.log(`🎨 Parsed ${filamentData.length} filament indices`);

    // Determine grid dimensions - try to find best rectangular fit
    const totalPixels = filamentData.length;
    let bestWidth = 1,
      bestHeight = totalPixels;

    // Find factors that create reasonable aspect ratios
    for (let w = 1; w <= Math.sqrt(totalPixels); w++) {
      if (totalPixels % w === 0) {
        const h = totalPixels / w;
        const aspectRatio = Math.max(w, h) / Math.min(w, h);
        if (aspectRatio < 20) {
          // Allow wider aspect ratios for painted textures
          bestWidth = w;
          bestHeight = h;
        }
      }
    }

    console.log(`🎨 Grid dimensions: ${bestWidth}×${bestHeight}`);

    // Count non-background pixels and analyze filament usage
    const nonBackgroundCount = filamentData.filter(f => f !== 0).length;
    const filamentCounts = new Map<number, number>();
    filamentData.forEach(f => {
      filamentCounts.set(f, (filamentCounts.get(f) || 0) + 1);
    });

    console.log(
      `🎨 Non-background pixels: ${nonBackgroundCount}/${totalPixels} (${((nonBackgroundCount / totalPixels) * 100).toFixed(1)}%)`
    );

    // Log filament usage distribution
    const sortedFilaments = Array.from(filamentCounts.entries()).sort(
      (a, b) => b[1] - a[1]
    );
    console.log(
      `🎨 Filament distribution: ${sortedFilaments.map(([f, c]) => `${f}(${c}px/${((c / totalPixels) * 100).toFixed(1)}%)`).join(', ')}`
    );

    // Find the most common non-background filament as primary
    const nonBackgroundFilamentCounts = new Map<number, number>();
    for (const filament of filamentData) {
      if (filament !== 0) {
        nonBackgroundFilamentCounts.set(
          filament,
          (nonBackgroundFilamentCounts.get(filament) || 0) + 1
        );
      }
    }

    let primaryFilamentIndex = 1;
    let maxCount = 0;
    for (const [filament, count] of nonBackgroundFilamentCounts) {
      if (count > maxCount) {
        maxCount = count;
        primaryFilamentIndex = filament;
      }
    }

    console.log(
      `🎨 Primary filament: ${primaryFilamentIndex} (${maxCount} pixels)`
    );

    return {
      width: bestWidth,
      height: bestHeight,
      filamentData,
      primaryFilamentIndex,
    };
  } catch (error) {
    console.error('Failed to decode hex paint data:', error);
    return null;
  }
}

// Helper function to convert hex color to RGB
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16) / 255,
        g: parseInt(result[2], 16) / 255,
        b: parseInt(result[3], 16) / 255,
      }
    : { r: 0, g: 0, b: 0 };
}

// Load mesh data from a single component
async function loadSingleComponentMesh(
  component: Component3MF,
  zip: JSZip
): Promise<{
  vertices: Float32Array;
  indices: Uint32Array;
  mesh?: Mesh3MF;
} | null> {
  const modelPath = component['@_p:path'];
  if (!modelPath) {
    return null;
  }

  // Remove leading slash if present
  const cleanPath = modelPath.startsWith('/')
    ? modelPath.substring(1)
    : modelPath;

  const modelFile = zip.file(cleanPath);
  if (!modelFile) {
    return null;
  }

  try {
    const modelXml = await modelFile.async('text');
    const parser = new XMLParser({
      ignoreAttributes: false,
      attributeNamePrefix: '@_',
      textNodeName: '#text',
      parseAttributeValue: true,
      trimValues: true,
      // ignoreNameSpace is not a valid option, removed
    });

    const doc = parser.parse(modelXml) as Document3MF;
    if (!doc.model?.resources?.object) {
      return null;
    }

    // Get the first object from the component model
    const objects = Array.isArray(doc.model.resources.object)
      ? doc.model.resources.object
      : [doc.model.resources.object];

    const targetObjectId = component['@_objectid'];
    const targetObject =
      objects.find(obj => obj['@_id'] === targetObjectId) || objects[0];

    if (!targetObject?.mesh) {
      return null;
    }

    const vertices = extractVerticesFromParsed(targetObject.mesh);
    const indices = extractIndicesFromParsed(targetObject.mesh);

    if (!vertices || !indices) {
      return null;
    }

    // Return the full mesh structure along with processed vertices/indices
    return { vertices, indices, mesh: targetObject.mesh };
  } catch {
    return null;
  }
}

// Multiply two 4x4 transformation matrices (both in column-major order)
function multiplyMatrices(a: Float32Array, b: Float32Array): Float32Array {
  const result = new Float32Array(16);

  // Matrix multiplication for 4x4 matrices in column-major order
  // result = a * b
  for (let col = 0; col < 4; col++) {
    for (let row = 0; row < 4; row++) {
      let sum = 0;
      for (let k = 0; k < 4; k++) {
        // a[row][k] * b[k][col] in column-major indexing
        sum += a[row + k * 4] * b[k + col * 4];
      }
      result[row + col * 4] = sum;
    }
  }

  return result;
}

// Message handler
self.addEventListener('message', async (event: MessageEvent<ParseRequest>) => {
  if (event.data.type === 'parse') {
    try {
      const plateContents = await parse3MFPlate(
        event.data.fileData,
        event.data.plateIndex
      );
      const response: ParseResponse = {
        type: 'success',
        plateContents,
      };
      self.postMessage(response);
    } catch (error) {
      const response: ParseResponse = {
        type: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
      };
      self.postMessage(response);
    }
  }
});

// Export for TypeScript
export {};
