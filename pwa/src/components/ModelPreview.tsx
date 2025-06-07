import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { STLLoader } from 'three-stdlib';
import { ThreeMFLoader } from 'three-stdlib';
import { FilamentRequirement, FilamentMapping, PlateInfo } from '../types/api';

interface ModelPreviewProps {
  fileId: string;
  filamentRequirements?: FilamentRequirement;
  filamentMappings?: FilamentMapping[];
  plates?: PlateInfo[];
  selectedPlateIndex?: number | null;
  className?: string;
}

const ModelPreview: React.FC<ModelPreviewProps> = ({
  fileId,
  filamentRequirements,
  filamentMappings = [],
  plates = [],
  selectedPlateIndex = null,
  className = '',
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const animationRef = useRef<number | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [initError, setInitError] = useState<string | null>(null);

  // Initialize Three.js scene
  useEffect(() => {
    if (!mountRef.current) {
      console.log('ModelPreview: mountRef not available');
      return;
    }

    console.log('ModelPreview: Initializing Three.js scene');
    const container = mountRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight || 300;

    try {
      // Check if WebGL is available by trying to create a context
      const canvas = document.createElement('canvas');
      const gl =
        canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) {
        throw new Error('WebGL is not supported by this browser');
      }

      // Scene
      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xf5f5f5);
      sceneRef.current = scene;
      console.log('ModelPreview: Scene created successfully');

      // Camera
      const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
      camera.position.set(0, 0, 50);
      cameraRef.current = camera;
      console.log('ModelPreview: Camera created successfully');

      // Renderer
      const renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        preserveDrawingBuffer: true,
      });
      renderer.setSize(width, height);
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      rendererRef.current = renderer;
      console.log('ModelPreview: Renderer created successfully');

      container.appendChild(renderer.domElement);

      // Lighting
      const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
      scene.add(ambientLight);

      const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
      directionalLight.position.set(1, 1, 1);
      directionalLight.castShadow = true;
      scene.add(directionalLight);
      console.log('ModelPreview: Lighting setup complete');

      // Controls (simple rotation animation)
      const animate = () => {
        if (meshRef.current) {
          meshRef.current.rotation.y += 0.005;
        }
        renderer.render(scene, camera);
        animationRef.current = requestAnimationFrame(animate);
      };
      animate();
      console.log('ModelPreview: Animation loop started');

      // Handle resize
      const handleResize = () => {
        if (!container) return;
        const newWidth = container.clientWidth;
        const newHeight = container.clientHeight || 300;

        camera.aspect = newWidth / newHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(newWidth, newHeight);
      };

      window.addEventListener('resize', handleResize);

      return () => {
        console.log('ModelPreview: Cleaning up Three.js scene');
        window.removeEventListener('resize', handleResize);
        if (animationRef.current) {
          cancelAnimationFrame(animationRef.current);
        }
        if (
          container &&
          renderer.domElement &&
          container.contains(renderer.domElement)
        ) {
          container.removeChild(renderer.domElement);
        }
        renderer.dispose();
      };
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown initialization error';
      console.error('ModelPreview: Error initializing Three.js scene:', error);
      setInitError(errorMessage);
    }
  }, []);

  // Load model
  useEffect(() => {
    if (!fileId || !sceneRef.current) {
      console.log('ModelPreview: No fileId or scene not ready');
      return;
    }

    if (initError) {
      console.log('ModelPreview: Skipping model load due to init error');
      return;
    }

    console.log('ModelPreview: Starting to load model with fileId:', fileId);
    setIsLoading(true);
    setError(null);

    // Set a timeout to prevent infinite loading
    const loadingTimeout = setTimeout(() => {
      console.error('ModelPreview: Model loading timed out after 30 seconds');
      setError('Model loading timed out. Please try again.');
      setIsLoading(false);
    }, 30000);

    const clearLoadingTimeout = () => {
      clearTimeout(loadingTimeout);
    };

    // Determine file type from file extension
    const fileExtension = fileId.toLowerCase().split('.').pop();
    const modelUrl = `/api/model/preview/${fileId}`;

    console.log('ModelPreview: File extension:', fileExtension);
    console.log('ModelPreview: Model URL:', modelUrl);

    const handleGeometry = (geometry: THREE.BufferGeometry) => {
      try {
        clearLoadingTimeout(); // Clear timeout on successful geometry processing
        console.log('ModelPreview: Processing geometry');

        // Remove existing mesh
        if (meshRef.current) {
          sceneRef.current?.remove(meshRef.current);
          meshRef.current = null;
        }

        // Create material with default color
        const material = new THREE.MeshLambertMaterial({
          color: getModelColor(0, filamentRequirements, filamentMappings),
        });

        // Create mesh
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        meshRef.current = mesh;

        // Center and scale the model
        geometry.computeBoundingBox();
        if (geometry.boundingBox) {
          const box = geometry.boundingBox;
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3());

          // Center the geometry
          geometry.translate(-center.x, -center.y, -center.z);

          // Scale to fit in view
          const maxDim = Math.max(size.x, size.y, size.z);
          const scale = 30 / maxDim;
          mesh.scale.setScalar(scale);

          console.log('ModelPreview: Geometry processed and added to scene');
          sceneRef.current!.add(mesh);
          setIsLoading(false);
        } else {
          throw new Error('Geometry bounding box could not be computed');
        }
      } catch (error) {
        clearLoadingTimeout();
        console.error('ModelPreview: Error processing geometry:', error);
        setError('Failed to process model geometry');
        setIsLoading(false);
      }
    };

    const handleProgress = (progress: ProgressEvent) => {
      console.log(
        'ModelPreview: Loading progress:',
        progress.loaded,
        '/',
        progress.total
      );
    };

    const handleError = (error: Error | ErrorEvent | unknown) => {
      clearLoadingTimeout(); // Clear timeout on error
      console.error('ModelPreview: Error loading model:', error);

      let errorMessage = 'Failed to load model for preview';
      if (error instanceof Error) {
        errorMessage = `Failed to load model: ${error.message}`;
      } else if (typeof error === 'string') {
        errorMessage = `Failed to load model: ${error}`;
      } else if (error && typeof error === 'object' && 'message' in error) {
        errorMessage = `Failed to load model: ${
          (error as { message: string }).message
        }`;
      }

      // Log additional context for debugging
      console.error('ModelPreview: Error context:', {
        fileId,
        fileExtension,
        modelUrl,
        initError,
        errorType: typeof error,
        errorName: error instanceof Error ? error.name : 'Unknown',
      });

      setError(errorMessage);
      setIsLoading(false);
    };

    // Choose appropriate loader based on file extension
    if (fileExtension === 'stl') {
      try {
        console.log('ModelPreview: Creating STL loader');
        const loader = new STLLoader();

        // Set up loading manager for better error handling
        const loadingManager = new THREE.LoadingManager();
        loadingManager.onLoad = () => {
          console.log('ModelPreview: STL loading completed');
        };
        loadingManager.onError = url => {
          console.error('ModelPreview: Loading manager error for URL:', url);
          handleError(new Error(`Failed to load resource: ${url}`));
        };

        loader.manager = loadingManager;
        loader.load(modelUrl, handleGeometry, handleProgress, handleError);
        console.log('ModelPreview: STL load initiated');
      } catch (loaderError) {
        console.error('ModelPreview: Error creating STL loader:', loaderError);
        setError('Failed to initialize STL loader');
        setIsLoading(false);
      }
    } else if (fileExtension === '3mf') {
      try {
        console.log('ModelPreview: Creating 3MF loader');
        const loader = new ThreeMFLoader();

        // Set up loading manager for better error handling
        const loadingManager = new THREE.LoadingManager();
        loadingManager.onLoad = () => {
          console.log('ModelPreview: 3MF loading completed');
        };
        loadingManager.onError = url => {
          console.error('ModelPreview: Loading manager error for URL:', url);
          handleError(new Error(`Failed to load resource: ${url}`));
        };

        loader.manager = loadingManager;
        loader.load(
          modelUrl,
          (object: THREE.Group) => {
            console.log('ModelPreview: Processing 3MF object');
            // ThreeMFLoader returns a Group, we need to extract the geometry
            // and handle potential multiple objects/materials
            const geometries: THREE.BufferGeometry[] = [];

            object.traverse(child => {
              if (child instanceof THREE.Mesh && child.geometry) {
                geometries.push(child.geometry);
              }
            });

            if (geometries.length > 0) {
              console.log(
                `ModelPreview: Found ${geometries.length} geometries in 3MF`
              );

              // Handle multiple geometries - for now just use the first one
              // TODO: In future, could merge geometries for complete model display
              if (geometries.length === 1) {
                handleGeometry(geometries[0]);
              } else {
                console.log(
                  `ModelPreview: Found ${geometries.length} geometries, using first one`
                );
                console.log(
                  `ModelPreview: Note - Multi-part 3MF models may not display completely`
                );
                handleGeometry(geometries[0]);
              }
            } else {
              handleError(new Error('No valid geometry found in 3MF file'));
            }
          },
          handleProgress,
          handleError
        );
        console.log('ModelPreview: 3MF load initiated');
      } catch (loaderError) {
        console.error('ModelPreview: Error creating 3MF loader:', loaderError);
        setError('Failed to initialize 3MF loader');
        setIsLoading(false);
      }
    } else {
      clearLoadingTimeout();
      console.log('ModelPreview: Unsupported file extension:', fileExtension);
      setError(`Unsupported file type: ${fileExtension}`);
      setIsLoading(false);
    }

    // Cleanup function
    return () => {
      clearLoadingTimeout();
    };
  }, [fileId, filamentRequirements, filamentMappings, initError, selectedPlateIndex]);

  // Update colors when filament mappings change
  useEffect(() => {
    if (!meshRef.current || !filamentRequirements) return;

    try {
      const newColor = getModelColor(0, filamentRequirements, filamentMappings);
      (meshRef.current.material as THREE.MeshLambertMaterial).color.setHex(
        newColor
      );
      console.log('ModelPreview: Updated material color');
    } catch (error) {
      console.error('ModelPreview: Error updating material color:', error);
    }
  }, [filamentMappings, filamentRequirements]);

  return (
    <div className={`model-preview ${className}`}>
      <div className="model-preview-header">
        <h3>
          Model Preview
          {plates.length > 1 && selectedPlateIndex !== null && (
            <span className="plate-indicator"> - Plate {selectedPlateIndex}</span>
          )}
          {plates.length > 1 && selectedPlateIndex === null && (
            <span className="plate-indicator"> - All Plates</span>
          )}
        </h3>
        {initError && (
          <span className="error-text">Initialization Error: {initError}</span>
        )}
        {!initError && isLoading && (
          <span className="loading-text">Loading model...</span>
        )}
        {!initError && error && <span className="error-text">{error}</span>}
      </div>
      <div
        ref={mountRef}
        className="model-preview-container"
        style={{
          width: '100%',
          height: '300px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          overflow: 'hidden',
          backgroundColor: initError ? '#f5f5f5' : 'transparent',
        }}
      >
        {initError && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#666',
              fontSize: '14px',
              textAlign: 'center',
              padding: '20px',
            }}
          >
            <div>
              <div>⚠️ 3D Preview Unavailable</div>
              <div style={{ marginTop: '8px' }}>{initError}</div>
            </div>
          </div>
        )}
      </div>
      {filamentRequirements && filamentRequirements.filament_count > 1 && (
        <div className="preview-note">
          <small>
            ⚠️ Multi-material models show simplified color preview. Actual print
            will use mapped filament colors.
          </small>
        </div>
      )}
      {plates.length > 1 && (
        <div className="preview-note">
          <small>
            📋 Multi-plate model detected. Preview shows{' '}
            {selectedPlateIndex !== null ? `Plate ${selectedPlateIndex} only` : 'combined view of all plates'}.
            {selectedPlateIndex !== null && (
              <span> Use plate selector above to change the target plate for slicing.</span>
            )}
          </small>
        </div>
      )}
    </div>
  );
};

/**
 * Get the color for a model part based on filament mappings
 */
function getModelColor(
  filamentIndex: number,
  filamentRequirements?: FilamentRequirement,
  filamentMappings: FilamentMapping[] = []
): number {
  // If we have filament requirements and mappings, try to use the mapped color
  if (filamentRequirements && filamentMappings.length > 0) {
    const mapping = filamentMappings.find(
      m => m.filament_index === filamentIndex
    );
    if (mapping) {
      // For now, use a simple color mapping based on AMS slot
      // This could be enhanced to query actual AMS colors
      const colors = [
        0xff6b6b, // Red
        0x4ecdc4, // Teal
        0x45b7d1, // Blue
        0x96ceb4, // Green
        0xffeaa7, // Yellow
        0xdda0dd, // Plum
        0xffa8a8, // Pink
        0x81ecec, // Cyan
      ];
      return colors[mapping.ams_slot_id % colors.length];
    }
  }

  // If we have filament requirements but no mapping, use the requirement color
  if (
    filamentRequirements &&
    filamentRequirements.filament_colors.length > filamentIndex
  ) {
    const colorStr = filamentRequirements.filament_colors[filamentIndex];
    if (colorStr && colorStr.startsWith('#')) {
      return parseInt(colorStr.substring(1), 16);
    }
  }

  // Default to a neutral color
  return 0x888888;
}

export default ModelPreview;
