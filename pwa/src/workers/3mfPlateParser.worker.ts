// Web Worker for parsing 3MF files and extracting plate data

import JSZip from 'jszip';
import type { ParsedPlateData } from '../types/3mf';
import { processPlate } from './3mf/plate';

// Message types
interface ParseRequest {
  type: 'parse';
  fileData: ArrayBuffer;
  plateIndex: number;
}

interface ParseResponse {
  type: 'success' | 'error';
  plateContents?: ParsedPlateData;
  error?: string;
}

// Main parsing function
async function parse3MFPlate(
  fileData: ArrayBuffer,
  plateIndex: number
): Promise<ParsedPlateData> {
  try {
    // Load the zip file
    const zip = new JSZip();
    const zipContents = await zip.loadAsync(fileData);

    // Process the specified plate
    return await processPlate(zipContents, plateIndex);
  } catch (error) {
    console.error('Error parsing 3MF file:', error);
    throw error;
  }
}

// Worker message handler
self.onmessage = async (event: MessageEvent<ParseRequest>) => {
  if (event.data.type === 'parse') {
    try {
      const { fileData, plateIndex } = event.data;
      const plateContents = await parse3MFPlate(fileData, plateIndex);

      const response: ParseResponse = {
        type: 'success',
        plateContents,
      };

      self.postMessage(response);
    } catch (error) {
      const response: ParseResponse = {
        type: 'error',
        error:
          error instanceof Error ? error.message : 'Unknown error occurred',
      };

      self.postMessage(response);
    }
  }
};

// Export types for TypeScript
export type { ParseRequest, ParseResponse };
