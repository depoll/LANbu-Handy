// Configuration file parsing for 3MF files

import { XMLParser } from 'fast-xml-parser';

const xmlParserOptions = {
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  textNodeName: '#text',
  parseAttributeValue: true,
  trimValues: true,
  processEntities: true,
  allowBooleanAttributes: true,
};

interface PlateConfig {
  name: string;
  filaments: string[];
}

interface ModelConfig {
  metadata?: {
    filament_info?: Array<{
      '@_id': number;
      '@_type': string;
      '@_color': string;
    }>;
  };
}

interface SliceInfo {
  filaments?: Array<{
    id: number;
    type: string;
    color: string;
  }>;
}

/**
 * Parse project_settings.config file
 */
export function parseProjectSettings(content: string): PlateConfig[] {
  const plates: PlateConfig[] = [];
  const lines = content.split('\n');

  let currentPlateName: string | null = null;
  let currentPlateFilaments: string[] = [];

  for (const line of lines) {
    const trimmedLine = line.trim();

    if (trimmedLine.startsWith('plate_name_')) {
      // Save previous plate if exists
      if (currentPlateName) {
        plates.push({
          name: currentPlateName,
          filaments: [...currentPlateFilaments],
        });
      }

      // Extract plate index and name
      const plateMatch = trimmedLine.match(/plate_name_(\d+)\s*=\s*(.+)/);
      if (plateMatch) {
        currentPlateName = plateMatch[2].trim();
        currentPlateFilaments = [];
      }
    } else if (trimmedLine.includes('filament_type_') && currentPlateName) {
      // Extract filament type
      const filamentMatch = trimmedLine.match(/filament_type_\d+\s*=\s*(.+)/);
      if (filamentMatch) {
        currentPlateFilaments.push(filamentMatch[1].trim());
      }
    }
  }

  // Don't forget the last plate
  if (currentPlateName) {
    plates.push({
      name: currentPlateName,
      filaments: [...currentPlateFilaments],
    });
  }

  return plates;
}

/**
 * Parse model_settings.config file
 */
export function parseModelSettings(xml: string): ModelConfig {
  const parser = new XMLParser(xmlParserOptions);
  const parsed = parser.parse(xml);

  // The structure can vary, so we need to handle different cases
  if (parsed.config) {
    return parsed.config as ModelConfig;
  }

  return {};
}

/**
 * Parse slice_info.config file
 */
export function parseSliceInfo(xml: string): SliceInfo {
  const parser = new XMLParser(xmlParserOptions);
  const parsed = parser.parse(xml);

  const sliceInfo: SliceInfo = {};

  // Extract filament information from slice info
  if (parsed.config?.metadata?.filament_info) {
    const filamentInfoArray = Array.isArray(
      parsed.config.metadata.filament_info
    )
      ? parsed.config.metadata.filament_info
      : [parsed.config.metadata.filament_info];

    sliceInfo.filaments = filamentInfoArray.map(
      (info: { '@_id': number; '@_type': string; '@_color': string }) => ({
        id: info['@_id'] || 0,
        type: info['@_type'] || '',
        color: info['@_color'] || '#FFFFFF',
      })
    );
  }

  return sliceInfo;
}

/**
 * Extract filament colors from various config sources
 */
export function extractFilamentColors(
  modelSettings: ModelConfig,
  sliceInfo: SliceInfo
): Record<number, string> {
  const colors: Record<number, string> = {};

  // Try slice info first (more reliable)
  if (sliceInfo.filaments) {
    sliceInfo.filaments.forEach(filament => {
      colors[filament.id] = filament.color;
    });
  }

  // Fallback to model settings
  if (modelSettings.metadata?.filament_info) {
    modelSettings.metadata.filament_info.forEach(info => {
      if (!colors[info['@_id']]) {
        colors[info['@_id']] = info['@_color'];
      }
    });
  }

  return colors;
}
