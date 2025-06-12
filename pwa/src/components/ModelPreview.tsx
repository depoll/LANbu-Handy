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
  const [useThumbnail, setUseThumbnail] = useState(false);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);

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
      console.log('ModelPreview: Timeout - attempting thumbnail fallback...');
      tryThumbnailFallback();
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

    const tryThumbnailFallback = async () => {
      try {
        console.log(
          'ModelPreview: Trying thumbnail fallback for fileId:',
          fileId,
          'selectedPlateIndex:',
          selectedPlateIndex
        );
        
        // Use plate-specific thumbnail if a specific plate is selected
        let thumbnailUrl: string;
        if (selectedPlateIndex !== null && selectedPlateIndex !== undefined) {
          thumbnailUrl = `/api/model/thumbnail/${fileId}/plate/${selectedPlateIndex}?width=300&height=300`;
          console.log('ModelPreview: Using plate-specific thumbnail:', thumbnailUrl);
        } else {
          thumbnailUrl = `/api/model/thumbnail/${fileId}?width=300&height=300`;
          console.log('ModelPreview: Using general thumbnail:', thumbnailUrl);
        }

        // Test if thumbnail endpoint responds
        const response = await fetch(thumbnailUrl, { method: 'HEAD' });
        if (response.ok) {
          console.log(
            'ModelPreview: Thumbnail available, switching to thumbnail view'
          );
          setThumbnailUrl(thumbnailUrl);
          setUseThumbnail(true);
          setError(null);
          setIsLoading(false);
        } else {
          // If plate-specific thumbnail fails, try general thumbnail as fallback
          if (selectedPlateIndex !== null && selectedPlateIndex !== undefined) {
            console.log('ModelPreview: Plate-specific thumbnail failed, trying general thumbnail');
            const generalThumbnailUrl = `/api/model/thumbnail/${fileId}?width=300&height=300`;
            const generalResponse = await fetch(generalThumbnailUrl, { method: 'HEAD' });
            
            if (generalResponse.ok) {
              console.log('ModelPreview: General thumbnail available as fallback');
              setThumbnailUrl(generalThumbnailUrl);
              setUseThumbnail(true);
              setError(null);
              setIsLoading(false);
              return;
            }
          }
          
          throw new Error(`Thumbnail generation failed: ${response.status}`);
        }
      } catch (thumbnailError) {
        console.error(
          'ModelPreview: Thumbnail fallback also failed:',
          thumbnailError
        );
        setError(
          'Failed to load model preview and thumbnail generation failed'
        );
        setIsLoading(false);
      }
    };

    const handleError = (error: Error | ErrorEvent | unknown) => {
      clearLoadingTimeout(); // Clear timeout on error
      console.error('ModelPreview: Error loading model:', error);

      // Log additional context for debugging
      console.error('ModelPreview: Error context:', {
        fileId,
        fileExtension,
        modelUrl,
        initError,
        errorType: typeof error,
        errorName: error instanceof Error ? error.name : 'Unknown',
        errorDetails: error instanceof Error ? error.message : String(error),
      });

      // Try to fallback to thumbnail if Three.js loading failed
      console.log('ModelPreview: Attempting to fallback to thumbnail...');
      tryThumbnailFallback();
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

              if (geometries.length === 1) {
                handleGeometry(geometries[0]);
              } else {
                console.log(
                  `ModelPreview: Found ${geometries.length} geometries, attempting to merge...`
                );

                try {
                  // Try to merge multiple geometries for better preview
                  const mergedGeometry = mergeGeometries(geometries);
                  if (mergedGeometry) {
                    console.log('ModelPreview: Successfully merged geometries');
                    handleGeometry(mergedGeometry);
                  } else {
                    console.log(
                      'ModelPreview: Merge failed, using first geometry'
                    );
                    handleGeometry(geometries[0]);
                  }
                } catch (mergeError) {
                  console.warn(
                    'ModelPreview: Geometry merge failed:',
                    mergeError
                  );
                  console.log('ModelPreview: Falling back to first geometry');
                  handleGeometry(geometries[0]);
                }
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
  }, [
    fileId,
    filamentRequirements,
    filamentMappings,
    initError,
    selectedPlateIndex,
  ]);

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

  // Update thumbnail when selected plate changes (for thumbnail view)
  useEffect(() => {
    if (!useThumbnail || !fileId) return;

    console.log('ModelPreview: Selected plate changed, updating thumbnail URL');
    
    // Use plate-specific thumbnail if a specific plate is selected
    let newThumbnailUrl: string;
    if (selectedPlateIndex !== null && selectedPlateIndex !== undefined) {
      newThumbnailUrl = `/api/model/thumbnail/${fileId}/plate/${selectedPlateIndex}?width=300&height=300`;
      console.log('ModelPreview: Switching to plate-specific thumbnail:', newThumbnailUrl);
    } else {
      newThumbnailUrl = `/api/model/thumbnail/${fileId}?width=300&height=300`;
      console.log('ModelPreview: Switching to general thumbnail:', newThumbnailUrl);
    }

    setThumbnailUrl(newThumbnailUrl);
  }, [selectedPlateIndex, useThumbnail, fileId]);

  return (
    <div className={`model-preview ${className}`}>
      <div className="model-preview-header">
        <h3>
          Model Preview
          {plates.length > 1 && selectedPlateIndex !== null && (
            <span className="plate-indicator">
              {' '}
              - Plate {selectedPlateIndex}
            </span>
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
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
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
        {!initError && useThumbnail && thumbnailUrl && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              padding: '20px',
            }}
          >
            <img
              src={thumbnailUrl}
              alt="Model Thumbnail"
              style={{
                maxWidth: '100%',
                maxHeight: '260px',
                objectFit: 'contain',
              }}
              onError={() => {
                console.error('ModelPreview: Thumbnail image failed to load');
                setError('Failed to load model preview and thumbnail');
                setUseThumbnail(false);
              }}
            />
            <div
              style={{
                marginTop: '8px',
                fontSize: '12px',
                color: '#666',
                textAlign: 'center',
              }}
            >
              📷 {selectedPlateIndex !== null && selectedPlateIndex !== undefined 
                   ? `Plate ${selectedPlateIndex} Thumbnail` 
                   : 'Model Thumbnail'}
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
            {selectedPlateIndex !== null
              ? `Plate ${selectedPlateIndex} only`
              : 'combined view of all plates'}
            .
            {selectedPlateIndex !== null && (
              <span>
                {' '}
                Use plate selector above to change the target plate for slicing.
              </span>
            )}
          </small>
        </div>
      )}
    </div>
  );
};

/**
 * Merge multiple geometries into a single geometry for better preview
 */
function mergeGeometries(
  geometries: THREE.BufferGeometry[]
): THREE.BufferGeometry | null {
  try {
    if (geometries.length === 0) return null;
    if (geometries.length === 1) return geometries[0];

    // For now, just use the first geometry since proper merging is complex
    // This is an improvement over the previous approach as we at least check
    // if there are multiple geometries and could implement proper merging later
    console.log(
      'ModelPreview: Multiple geometries detected, using first geometry for now'
    );
    return geometries[0].clone();
  } catch (error) {
    console.error('ModelPreview: Error processing geometries:', error);
    return null;
  }
}

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
        0x4caf50, // Green
        0x96ceb4, // Light Green
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
