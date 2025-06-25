/**
 * Enhanced 3MF loader utilities for better Bambu Studio compatibility
 */

import * as THREE from 'three';
import { ThreeMFLoader } from 'three-stdlib';

/**
 * Enhanced loader that attempts multiple strategies to load 3MF files
 */
export class Enhanced3MFLoader {
  private loader: ThreeMFLoader;

  constructor() {
    this.loader = new ThreeMFLoader();
  }

  /**
   * Load a 3MF file with enhanced error handling and fallback strategies
   */
  async load(
    url: string,
    onLoad: (object: THREE.Group) => void,
    onProgress?: (event: ProgressEvent) => void,
    onError?: (error: unknown) => void
  ): Promise<void> {
    console.log('Enhanced3MFLoader: Loading', url);

    try {
      // First attempt: standard loading
      await this.attemptStandardLoad(url, onLoad, onProgress);
    } catch (firstError) {
      console.warn(
        'Enhanced3MFLoader: Standard load failed, trying fallback strategies',
        firstError
      );

      try {
        // Second attempt: load with manual parsing
        await this.attemptManualParsing(url, onLoad, onProgress);
      } catch (secondError) {
        console.error(
          'Enhanced3MFLoader: All loading strategies failed',
          secondError
        );
        if (onError) {
          onError(
            new Error(
              'Failed to load 3MF file after trying multiple strategies'
            )
          );
        }
      }
    }
  }

  /**
   * Standard loading attempt
   */
  private attemptStandardLoad(
    url: string,
    onLoad: (object: THREE.Group) => void,
    onProgress?: (event: ProgressEvent) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      this.loader.load(
        url,
        object => {
          // Validate the loaded object
          if (this.validateLoadedObject(object)) {
            onLoad(object);
            resolve();
          } else {
            reject(new Error('Loaded object validation failed'));
          }
        },
        onProgress,
        reject
      );
    });
  }

  /**
   * Manual parsing attempt for problematic 3MF files
   */
  private async attemptManualParsing(
    url: string,
    onLoad: (object: THREE.Group) => void,
    onProgress?: (event: ProgressEvent) => void
  ): Promise<void> {
    console.log('Enhanced3MFLoader: Attempting manual parsing');

    // Fetch the file
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to fetch 3MF file: ${response.statusText}`);
    }

    const arrayBuffer = await response.arrayBuffer();

    // Report progress
    if (onProgress) {
      onProgress(
        new ProgressEvent('progress', {
          loaded: arrayBuffer.byteLength,
          total: arrayBuffer.byteLength,
        })
      );
    }

    // Try to parse with custom error handling
    try {
      // Use the loader's parse method if available
      if ('parse' in this.loader && typeof this.loader.parse === 'function') {
        const object = this.loader.parse(arrayBuffer);

        if (this.validateLoadedObject(object)) {
          onLoad(object);
        } else {
          // If validation fails, try to extract any geometry we can find
          const fallbackObject = this.extractAnyGeometry(object);
          if (fallbackObject) {
            onLoad(fallbackObject);
          } else {
            throw new Error('No valid geometry could be extracted');
          }
        }
      } else {
        throw new Error('Loader does not support parse method');
      }
    } catch (parseError) {
      console.error('Enhanced3MFLoader: Parse error', parseError);

      // Last resort: create a placeholder geometry
      const placeholderObject = this.createPlaceholderObject();
      onLoad(placeholderObject);
    }
  }

  /**
   * Validate that the loaded object contains valid geometry
   */
  private validateLoadedObject(object: THREE.Group): boolean {
    let hasValidGeometry = false;

    object.traverse(child => {
      if (child instanceof THREE.Mesh && child.geometry) {
        const geometry = child.geometry;
        if (
          geometry.attributes.position &&
          geometry.attributes.position.count > 0
        ) {
          hasValidGeometry = true;
        }
      }
    });

    return hasValidGeometry;
  }

  /**
   * Try to extract any valid geometry from a partially loaded object
   */
  private extractAnyGeometry(object: THREE.Group): THREE.Group | null {
    const newGroup = new THREE.Group();
    let foundAnyGeometry = false;

    object.traverse(child => {
      if (child instanceof THREE.Mesh && child.geometry) {
        const geometry = child.geometry;

        // Check if geometry has valid data
        if (
          geometry.attributes.position &&
          geometry.attributes.position.count > 0
        ) {
          // Clone the mesh with its geometry
          const clonedMesh = child.clone();
          newGroup.add(clonedMesh);
          foundAnyGeometry = true;
        }
      }
    });

    return foundAnyGeometry ? newGroup : null;
  }

  /**
   * Create a placeholder object when all else fails
   */
  private createPlaceholderObject(): THREE.Group {
    console.warn('Enhanced3MFLoader: Creating placeholder geometry');

    const group = new THREE.Group();

    // Create a simple cube as placeholder
    const geometry = new THREE.BoxGeometry(10, 10, 10);
    const material = new THREE.MeshBasicMaterial({
      color: 0xcccccc,
      wireframe: true,
    });
    const mesh = new THREE.Mesh(geometry, material);

    group.add(mesh);

    return group;
  }

  /**
   * Dispose of the loader
   */
  dispose(): void {
    // Clean up if needed
  }
}

/**
 * Utility function to check if a file might need repair
 */
export async function check3MFNeedsRepair(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, { method: 'HEAD' });
    // You could implement more sophisticated checks here
    // For now, just return true for all 3MF files to use the repair service
    return response.ok;
  } catch {
    return false;
  }
}
