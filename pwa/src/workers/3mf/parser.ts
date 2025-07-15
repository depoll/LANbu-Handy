// Core 3MF model parsing logic

import { XMLParser } from 'fast-xml-parser';
import type { Model3MF, Object3MF } from '../../types/3mf';

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
 * Parse the main .model file content
 */
export function parse3mfModel(xml: string): Model3MF {
  const parser = new XMLParser(xmlParserOptions);
  return parser.parse(xml) as Model3MF;
}

/**
 * Extract objects from the model
 */
export function extractObjects(model: Model3MF): Object3MF[] {
  const objects: Object3MF[] = [];

  if (model.model?.resources?.object) {
    const objectData = model.model.resources.object;
    if (Array.isArray(objectData)) {
      objects.push(...objectData);
    } else {
      objects.push(objectData);
    }
  }

  return objects;
}

/**
 * Find object by ID
 */
export function findObjectById(
  objects: Object3MF[],
  id: string
): Object3MF | undefined {
  return objects.find(obj => obj['@_id'] === id);
}
