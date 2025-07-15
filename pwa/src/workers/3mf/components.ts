// Component processing for 3MF files

import JSZip from 'jszip';
import { XMLParser } from 'fast-xml-parser';
import type {
  Object3MF,
  Component3MF,
  Item3MF,
  PlateObject,
  Mesh3MF,
} from '../../types/3mf';
import { extractVertices, extractIndices } from './geometry';
import { parseTransformMatrix, multiplyMatrices } from '../../utils/3d-math';

const xmlParserOptions = {
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  textNodeName: '#text',
  parseAttributeValue: true,
  trimValues: true,
  processEntities: true,
  allowBooleanAttributes: true,
};

/**
 * Load a single component's mesh data
 */
async function loadSingleComponentMesh(
  component: Component3MF,
  zipContents: JSZip
): Promise<{
  vertices: Float32Array;
  indices: Uint32Array;
  mesh: Mesh3MF;
} | null> {
  const componentPath = component['@_p:path'];
  if (!componentPath) return null;

  // Path is relative to the main model file
  const modelFile = zipContents.file(/3D\/.*\.model$/i)?.[0];
  if (!modelFile) return null;

  const basePath = modelFile.name.substring(0, modelFile.name.lastIndexOf('/'));
  const fullPath = `${basePath}${componentPath}`;

  const componentFile = zipContents.file(fullPath);
  if (!componentFile) return null;

  const componentXml = await componentFile.async('text');
  const parser = new XMLParser(xmlParserOptions);
  const componentDoc = parser.parse(componentXml) as {
    model?: { resources?: { object?: Object3MF | Object3MF[] } };
  };

  // Find the first mesh object in the component file
  const objects = componentDoc.model?.resources?.object;
  if (!objects) return null;

  const objectArray = Array.isArray(objects) ? objects : [objects];
  const meshObject = objectArray.find(obj => obj.mesh);

  if (meshObject && meshObject.mesh) {
    const vertices = extractVertices(meshObject.mesh);
    const indices = extractIndices(meshObject.mesh);

    if (vertices && indices) {
      return { vertices, indices, mesh: meshObject.mesh };
    }
  }

  return null;
}

/**
 * Recursively process components to build plate objects
 */
async function processComponentRecursive(
  component: Component3MF,
  parentTransform: Float32Array,
  objects: Object3MF[],
  zipContents: JSZip,
  filamentColors: Record<number, string>,
  processedComponents: Set<string> = new Set()
): Promise<PlateObject[]> {
  const plateObjects: PlateObject[] = [];

  // Calculate the combined transform
  const componentTransform = component['@_transform']
    ? parseTransformMatrix(component['@_transform'])
    : new Float32Array(16);
  componentTransform.fill(0);
  componentTransform[0] = 1;
  componentTransform[5] = 1;
  componentTransform[10] = 1;
  componentTransform[15] = 1;

  const combinedTransform = multiplyMatrices(
    parentTransform,
    componentTransform
  );

  // Check if this is an external component (has p:path)
  if (component['@_p:path']) {
    // Prevent infinite loops
    const componentKey = `${component['@_p:path']}_${component['@_objectid']}`;
    if (processedComponents.has(componentKey)) {
      return plateObjects;
    }
    processedComponents.add(componentKey);

    // Load external component
    const meshData = await loadSingleComponentMesh(component, zipContents);
    if (meshData) {
      plateObjects.push({
        id: component['@_objectid'],
        type: 'component',
        vertices: meshData.vertices,
        indices: meshData.indices,
        transform: combinedTransform,
        filamentColors,
      });
    }
  } else {
    // Internal component reference
    const referencedObject = objects.find(
      obj => obj['@_id'] === component['@_objectid']
    );
    if (referencedObject) {
      if (referencedObject.mesh) {
        // Direct mesh
        const vertices = extractVertices(referencedObject.mesh);
        const indices = extractIndices(referencedObject.mesh);

        if (vertices && indices) {
          plateObjects.push({
            id: referencedObject['@_id'],
            type: 'component',
            vertices,
            indices,
            transform: combinedTransform,
            filamentColors,
          });
        }
      } else if (referencedObject.components?.component) {
        // Nested components
        const nestedComponents = Array.isArray(
          referencedObject.components.component
        )
          ? referencedObject.components.component
          : [referencedObject.components.component];

        for (const nestedComponent of nestedComponents) {
          const nestedObjects = await processComponentRecursive(
            nestedComponent,
            combinedTransform,
            objects,
            zipContents,
            filamentColors,
            processedComponents
          );
          plateObjects.push(...nestedObjects);
        }
      }
    }
  }

  return plateObjects;
}

/**
 * Load component-based mesh
 */
export async function loadComponentMesh(
  object: Object3MF,
  item: Item3MF,
  objects: Object3MF[],
  zipContents: JSZip,
  filamentColors: Record<number, string>
): Promise<PlateObject[] | null> {
  if (!object.components?.component) {
    return null;
  }

  const itemTransform = item['@_transform']
    ? parseTransformMatrix(item['@_transform'])
    : new Float32Array(16);
  itemTransform.fill(0);
  itemTransform[0] = 1;
  itemTransform[5] = 1;
  itemTransform[10] = 1;
  itemTransform[15] = 1;

  const components = Array.isArray(object.components.component)
    ? object.components.component
    : [object.components.component];

  const plateObjects: PlateObject[] = [];
  const processedComponents = new Set<string>();

  for (const component of components) {
    const componentObjects = await processComponentRecursive(
      component,
      itemTransform,
      objects,
      zipContents,
      filamentColors,
      processedComponents
    );
    plateObjects.push(...componentObjects);
  }

  return plateObjects.length > 0 ? plateObjects : null;
}
