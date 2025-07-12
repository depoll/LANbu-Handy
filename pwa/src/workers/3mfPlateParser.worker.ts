import JSZip from 'jszip';
import { XMLParser } from 'fast-xml-parser';

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
      ignoreNameSpace: true, // Remove namespace prefixes to handle p:paint_color
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
          ignoreNameSpace: true,
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

          // Load the component's mesh
          const componentMesh = await loadSingleComponentMesh(
            component,
            contents
          );
          if (!componentMesh) {
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

          // Debug logging for multi-material detection
          console.log('Multi-material check:', {
            projectFilamentColorsLength: projectFilamentColors.length,
            extruderMapSize: extruderMap.size,
            componentArrayLength: componentArray.length,
            plateObjectsLength: plateObjects.length,
            componentId,
            objectId,
          });

          // Check if this is a single-component multi-material model
          // (has more project colors than we have objects, and this is the only component)
          if (
            projectFilamentColors.length > 1 &&
            componentArray.length === 1 &&
            plateObjects.length === 0
          ) {
            console.log(
              'Creating multi-material objects for component:',
              componentId
            );
            // Create separate objects for each filament color with slight offsets to make them visible
            for (
              let colorIndex = 0;
              colorIndex < projectFilamentColors.length;
              colorIndex++
            ) {
              // Create a copy of the transform and add a small offset so objects don't overlap completely
              const offsetTransform = new Float32Array(finalTransform);
              // Add small X offset: 0.1mm per color index
              offsetTransform[12] += colorIndex * 0.1;

              plateObjects.push({
                id: `${objectId}_component_${componentId}_filament_${colorIndex}`,
                vertices: componentMesh.vertices,
                indices: componentMesh.indices,
                transform: offsetTransform,
                filamentIndex: colorIndex,
              });
              console.log(
                `Created component object for filament ${colorIndex} with color ${projectFilamentColors[colorIndex]} at offset ${colorIndex * 0.1}mm`
              );
            }
          } else {
            // Normal single-material or properly mapped multi-material component
            plateObjects.push({
              id: `${objectId}_component_${componentId}`,
              vertices: componentMesh.vertices,
              indices: componentMesh.indices,
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
    // 3x4 matrix - convert to 4x4
    return new Float32Array([
      values[0],
      values[1],
      values[2],
      0,
      values[3],
      values[4],
      values[5],
      0,
      values[6],
      values[7],
      values[8],
      0,
      values[9],
      values[10],
      values[11],
      1,
    ]);
  } else if (values.length === 16) {
    // Already 4x4
    return new Float32Array(values);
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
  if (!mesh.triangles || !mesh.triangles.triangle || !mesh.vertices) {
    return null;
  }

  const triangleArray = Array.isArray(mesh.triangles.triangle)
    ? mesh.triangles.triangle
    : [mesh.triangles.triangle];

  const vertexArray = Array.isArray(mesh.vertices.vertex)
    ? mesh.vertices.vertex
    : [mesh.vertices.vertex];

  // Check if any triangles have paint colors
  const hasPaintColors = triangleArray.some(
    t => t['@_paint_color'] !== undefined || t['@_p:paint_color'] !== undefined
  );
  if (!hasPaintColors) {
    return null;
  }

  // Create vertex color array (RGB, 3 floats per vertex)
  const vertexColors = new Float32Array(vertexArray.length * 3);

  // Initialize all vertices to default color (first project color or black)
  const defaultColor = hexToRgb(projectColors[0] || '#000000');
  for (let i = 0; i < vertexArray.length; i++) {
    vertexColors[i * 3] = defaultColor.r;
    vertexColors[i * 3 + 1] = defaultColor.g;
    vertexColors[i * 3 + 2] = defaultColor.b;
  }

  // Count paint colors for debugging
  const paintColorCounts: { [key: string]: number } = {};
  triangleArray.forEach(t => {
    const pc = t['@_paint_color'] || t['@_p:paint_color'] || 'default';
    paintColorCounts[pc] = (paintColorCounts[pc] || 0) + 1;
  });
  console.log('Paint color distribution:', paintColorCounts);
  console.log('Project colors:', projectColors);
  console.log(
    'Sample triangle with paint_color:',
    triangleArray.find(t => t['@_paint_color'] || t['@_p:paint_color'])
  );

  // Map paint color indices to RGB colors
  const paintColorMap = new Map<string, { r: number; g: number; b: number }>();

  // Paint color mappings based on Valentine Dragon analysis:
  // No paint_color = default (first filament - Black)
  // "0C" (hex 12) = second filament (Green) - 25,508 triangles
  // "8" = third filament (Red) - 2,738 triangles
  const paintIndexToExtruder: { [key: string]: number } = {
    '0C': 1, // Second filament (Green)
    '8': 2, // Third filament (Red)
    '4': 3, // Fourth filament (if exists)
    '0': 0, // First filament
    '12': 1, // Alternative decimal representation of 0C
  };

  // Apply triangle colors to vertices
  triangleArray.forEach((triangle: Triangle3MF) => {
    const paintColor = triangle['@_paint_color'] || triangle['@_p:paint_color'];
    if (paintColor) {
      // Get color for this paint index
      let color = paintColorMap.get(paintColor);
      if (!color) {
        const extruderIndex = paintIndexToExtruder[paintColor] ?? 0;
        const hexColor = projectColors[extruderIndex] || '#000000';
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
): Promise<{ vertices: Float32Array; indices: Uint32Array } | null> {
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
      ignoreNameSpace: true,
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

    return { vertices, indices };
  } catch {
    return null;
  }
}

// Multiply two 4x4 transformation matrices
function multiplyMatrices(a: Float32Array, b: Float32Array): Float32Array {
  const result = new Float32Array(16);

  // Matrix multiplication for 4x4 matrices
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
