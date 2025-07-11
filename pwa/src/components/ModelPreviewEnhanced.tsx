import {
  useEffect,
  useRef,
  useState,
  useCallback,
  useImperativeHandle,
  forwardRef,
} from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  FilamentRequirement,
  FilamentMapping,
  PlateInfo,
  AMSStatusResponse,
} from '../types/api';

// Web Worker types
interface PlateObject {
  id: string;
  vertices: Float32Array;
  indices: Uint32Array;
  transform: Float32Array;
  filamentIndex: number;
}

interface PlateContents {
  plateIndex: number;
  objects: PlateObject[];
}

export interface ModelPreviewRef {
  capturePreview: () => Promise<string>;
}

interface ModelPreviewProps {
  fileId: string;
  filamentRequirements?: FilamentRequirement;
  filamentMappings?: FilamentMapping[];
  amsStatus?: AMSStatusResponse | null;
  plates?: PlateInfo[];
  selectedPlateIndex?: number | null;
  className?: string;
}

const ModelPreviewEnhanced = forwardRef<ModelPreviewRef, ModelPreviewProps>(
  (
    {
      fileId,
      filamentRequirements,
      filamentMappings = [],
      amsStatus,
      plates = [],
      selectedPlateIndex = null,
      className = '',
    },
    ref
  ) => {
    const mountRef = useRef<HTMLDivElement>(null);
    const sceneRef = useRef<THREE.Scene | null>(null);
    const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
    const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
    const plateObjectsRef = useRef<Map<string, THREE.Mesh>>(new Map());
    const animationRef = useRef<number | null>(null);
    const workerRef = useRef<Worker | null>(null);
    const currentPlateDataRef = useRef<PlateContents | null>(null);

    const [isLoading, setIsLoading] = useState(true);
    const [loadingProgress, setLoadingProgress] = useState({
      message: 'Loading model...',
      percent: 0,
    });
    const [error, setError] = useState<string | null>(null);
    const [initError, setInitError] = useState<string | null>(null);
    const [useThumbnail, setUseThumbnail] = useState(false);
    const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
    const [isWebGLAvailable, setIsWebGLAvailable] = useState(true);

    // Helper function to get filament color from AMS status
    const getFilamentColor = useCallback(
      (filamentIndex: number): number => {
        const mapping = filamentMappings.find(
          m => m.filament_index === filamentIndex
        );

        console.log(
          `Getting color for filament ${filamentIndex}, mapping:`,
          mapping
        );

        if (mapping && amsStatus) {
          // Check if it's external spool
          if (
            (mapping.ams_unit_id === 254 || mapping.ams_unit_id === 255) &&
            amsStatus.external_spool?.available
          ) {
            const color = amsStatus.external_spool.color;
            console.log(`External spool color: ${color}`);
            if (color && color.startsWith('#')) {
              const colorValue = parseInt(color.substring(1), 16);
              console.log(
                `Returning external spool color: 0x${colorValue.toString(16)}`
              );
              return colorValue;
            }
          }

          // Check AMS units
          if (amsStatus.ams_units) {
            const unit = amsStatus.ams_units.find(
              u => u.unit_id === mapping.ams_unit_id
            );
            if (unit) {
              const filament = unit.filaments.find(
                f => f.slot_id === mapping.ams_slot_id
              );
              console.log(
                `Found filament in AMS ${mapping.ams_unit_id} slot ${mapping.ams_slot_id}:`,
                filament
              );
              if (
                filament &&
                filament.color &&
                filament.color.startsWith('#')
              ) {
                // Extract only the RGB part, ignoring alpha channel
                const colorHex = filament.color.substring(1);
                const rgbHex =
                  colorHex.length > 6 ? colorHex.substring(0, 6) : colorHex;
                const colorValue = parseInt(rgbHex, 16);
                console.log(
                  `Returning AMS color: 0x${colorValue.toString(16)} from ${filament.color} (RGB: ${rgbHex})`
                );
                return colorValue;
              }
            }
          }
        }

        // Use filament requirement color if available
        if (
          filamentRequirements &&
          filamentRequirements.filament_colors.length > filamentIndex
        ) {
          const colorStr = filamentRequirements.filament_colors[filamentIndex];
          console.log(
            `Using filament requirement color for index ${filamentIndex}: ${colorStr}`
          );
          if (colorStr && colorStr.startsWith('#')) {
            const colorValue = parseInt(colorStr.substring(1), 16);
            console.log(
              `Returning requirement color: 0x${colorValue.toString(16)}`
            );
            return colorValue;
          }
        }

        // Fallback colors for unmapped filaments (red-ish to indicate unmapped)
        const fallbackColors = [
          0xff4444, // Bright red
          0xff6666, // Light red
          0xff8888, // Lighter red
          0xffaaaa, // Very light red
        ];

        const fallbackColor =
          fallbackColors[filamentIndex % fallbackColors.length];
        console.log(
          `Using fallback color for index ${filamentIndex}: 0x${fallbackColor.toString(16)}`
        );
        return fallbackColor;
      },
      [filamentMappings, amsStatus, filamentRequirements]
    );

    // Helper function to create material with proper color
    const createFilamentMaterial = useCallback(
      (filamentIndex: number): THREE.Material => {
        const isMapped = filamentMappings.some(
          m => m.filament_index === filamentIndex
        );
        const color = getFilamentColor(filamentIndex);

        if (!isMapped) {
          // Pulsing material for unmapped filaments
          const material = new THREE.MeshPhongMaterial({
            color: new THREE.Color(color),
            emissive: new THREE.Color(color),
            emissiveIntensity: 0.2,
          });

          // Store original emissive intensity for animation
          // Using userData to avoid TypeScript any type
          material.userData.originalEmissiveIntensity = 0.2;
          material.userData.isUnmapped = true;

          return material;
        }

        // Normal material for mapped filaments
        return new THREE.MeshPhongMaterial({
          color: new THREE.Color(color),
          shininess: 100,
        });
      },
      [filamentMappings, getFilamentColor]
    );

    // Render plate objects from worker data
    const renderPlateObjects = useCallback(
      (plateContents: PlateContents) => {
        if (!sceneRef.current) return;

        console.log('renderPlateObjects called with:', plateContents);

        // Clear ALL existing objects from the scene (except lights)
        const objectsToRemove: THREE.Object3D[] = [];
        sceneRef.current.traverse(child => {
          if (child instanceof THREE.Mesh || child instanceof THREE.Group) {
            if (!(child instanceof THREE.Light)) {
              objectsToRemove.push(child);
            }
          }
        });

        objectsToRemove.forEach(obj => {
          sceneRef.current?.remove(obj);
          if (obj instanceof THREE.Mesh) {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
              if (Array.isArray(obj.material)) {
                obj.material.forEach(m => m.dispose());
              } else {
                obj.material.dispose();
              }
            }
          }
        });

        plateObjectsRef.current.clear();

        // Create group for all objects
        const group = new THREE.Group();
        group.name = `plate_group_${plateContents.plateIndex}`;
        const boundingBox = new THREE.Box3();

        // Process each object
        plateContents.objects.forEach(obj => {
          // Create geometry from object data
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute(
            'position',
            new THREE.BufferAttribute(obj.vertices, 3)
          );
          geometry.setIndex(new THREE.BufferAttribute(obj.indices, 1));
          geometry.computeVertexNormals();

          // Create material with filament color
          const material = createFilamentMaterial(obj.filamentIndex);

          // Create mesh
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = `plate_object_${obj.id}`;
          mesh.userData = { filamentIndex: obj.filamentIndex };

          // Apply transform
          const matrix = new THREE.Matrix4();
          matrix.fromArray(obj.transform);

          // Log transform details
          console.log(`Object ${obj.id} transform:`, {
            matrix: obj.transform,
            position: new THREE.Vector3().setFromMatrixPosition(matrix),
          });

          mesh.applyMatrix4(matrix);

          mesh.castShadow = true;
          mesh.receiveShadow = true;

          group.add(mesh);
          plateObjectsRef.current.set(mesh.name, mesh);

          // Update bounding box
          geometry.computeBoundingBox();
          if (geometry.boundingBox) {
            boundingBox.expandByObject(mesh);
          }
        });

        // Center and scale the group
        if (!boundingBox.isEmpty()) {
          const center = boundingBox.getCenter(new THREE.Vector3());
          const size = boundingBox.getSize(new THREE.Vector3());

          console.log('Bounding box info:', {
            center: { x: center.x, y: center.y, z: center.z },
            size: { x: size.x, y: size.y, z: size.z },
            min: boundingBox.min,
            max: boundingBox.max,
          });

          // Center the group
          group.position.sub(center);

          // Scale to fit in view
          const maxDim = Math.max(size.x, size.y, size.z);
          // Use a more conservative scale for better visibility
          const targetSize = 50; // Target size in scene units
          const scale = targetSize / maxDim;
          group.scale.setScalar(scale);

          console.log('Scaling info:', {
            maxDim,
            scale,
            targetSize,
          });

          sceneRef.current.add(group);
          console.log('Added group to scene, forcing render...');

          // Adjust camera to fit the model
          if (
            cameraRef.current &&
            cameraRef.current instanceof THREE.PerspectiveCamera
          ) {
            // Set camera distance based on scaled size
            const scaledSize = maxDim * scale;
            const distance = scaledSize * 1.5;
            cameraRef.current.position.set(
              distance * 0.7,
              distance * 0.5,
              distance
            );
            cameraRef.current.lookAt(0, 0, 0);
            cameraRef.current.updateProjectionMatrix();
          }

          // Force a render
          if (rendererRef.current && cameraRef.current && sceneRef.current) {
            console.log('Forcing render with:', {
              renderer: !!rendererRef.current,
              camera: !!cameraRef.current,
              scene: !!sceneRef.current,
              sceneChildren: sceneRef.current.children.length,
            });
            rendererRef.current.render(sceneRef.current, cameraRef.current);
          } else {
            console.log('Cannot render - missing components:', {
              renderer: !!rendererRef.current,
              camera: !!cameraRef.current,
              scene: !!sceneRef.current,
            });
          }
        } else {
          console.log('No objects to render or empty bounding box');
        }
      },
      [createFilamentMaterial]
    );

    // Standard model loading (fallback)
    const loadStandardModel = useCallback(() => {
      // Implementation similar to original ModelPreview
      // This is a simplified version - you would copy the logic from the original
      setUseThumbnail(true);
      setThumbnailUrl(`/api/model/thumbnail/${fileId}?width=300&height=300`);
      setIsLoading(false);
    }, [fileId]);

    // Handle load errors
    const handleLoadError = useCallback(
      (error: Error) => {
        console.error('Model loading error:', error);
        setError(error.message);
        setIsLoading(false);

        // Try thumbnail fallback
        const thumbnailUrl =
          selectedPlateIndex !== null
            ? `/api/model/thumbnail/${fileId}/plate/${selectedPlateIndex}?width=300&height=300`
            : `/api/model/thumbnail/${fileId}?width=300&height=300`;

        setThumbnailUrl(thumbnailUrl);
        setUseThumbnail(true);
      },
      [fileId, selectedPlateIndex]
    );

    // Initialize Three.js scene
    useEffect(() => {
      const mount = mountRef.current;
      if (!mount) return;

      try {
        // Check WebGL availability
        const canvas = document.createElement('canvas');
        const gl =
          canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (!gl) {
          console.error('WebGL not available');
          throw new Error('WebGL is not supported by this browser');
        }
        console.log('WebGL context created successfully');

        // Scene
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0xf5f5f5);
        sceneRef.current = scene;

        // Camera
        const width = mount.clientWidth;
        const height = mount.clientHeight || 300;
        const camera = new THREE.PerspectiveCamera(
          75,
          width / height,
          0.1,
          1000
        );
        camera.position.set(0, 0, 50);
        cameraRef.current = camera;

        // Renderer
        console.log('Creating Three.js renderer...');
        const renderer = new THREE.WebGLRenderer({
          antialias: true,
          alpha: true,
          preserveDrawingBuffer: true,
        });
        renderer.setSize(width, height);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        rendererRef.current = renderer;

        mount.appendChild(renderer.domElement);
        console.log('Renderer created and added to DOM');

        // Add orbit controls
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.rotateSpeed = 0.5;
        controls.zoomSpeed = 0.8;
        controls.minDistance = 10;
        controls.maxDistance = 200;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        const directionalLight1 = new THREE.DirectionalLight(0xffffff, 0.4);
        directionalLight1.position.set(1, 1, 1);
        directionalLight1.castShadow = true;
        scene.add(directionalLight1);

        const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.2);
        directionalLight2.position.set(-1, 1, -1);
        scene.add(directionalLight2);

        // Animation loop with pulsing for unmapped materials
        const animate = () => {
          // Update controls
          controls.update();

          // Pulse unmapped materials
          const time = Date.now() * 0.003;
          plateObjectsRef.current.forEach(mesh => {
            const material = mesh.material as THREE.MeshPhongMaterial;
            if (material.userData.isUnmapped) {
              material.emissiveIntensity = 0.2 + Math.sin(time) * 0.15;
            }
          });

          renderer.render(scene, camera);
          animationRef.current = requestAnimationFrame(animate);
        };
        animate();

        // Handle resize
        const handleResize = () => {
          if (!mount) return;
          const newWidth = mount.clientWidth;
          const newHeight = mount.clientHeight || 300;

          camera.aspect = newWidth / newHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(newWidth, newHeight);
        };

        window.addEventListener('resize', handleResize);

        return () => {
          window.removeEventListener('resize', handleResize);
          if (animationRef.current) {
            cancelAnimationFrame(animationRef.current);
          }
          if (
            mount &&
            renderer.domElement &&
            mount.contains(renderer.domElement)
          ) {
            mount.removeChild(renderer.domElement);
          }
          renderer.dispose();
        };
      } catch (error) {
        const errorMessage =
          error instanceof Error
            ? error.message
            : 'Unknown initialization error';
        setInitError(errorMessage);
        setIsWebGLAvailable(false);
      }
    }, []);

    // Initialize Web Worker
    useEffect(() => {
      const worker = new Worker(
        new URL('../workers/3mfPlateParser.worker.ts', import.meta.url),
        { type: 'module' }
      );
      workerRef.current = worker;

      return () => {
        worker.terminate();
      };
    }, []);

    // Update colors in real-time when filament mappings change
    useEffect(() => {
      if (!sceneRef.current || plateObjectsRef.current.size === 0) return;

      console.log(
        'Updating colors for',
        plateObjectsRef.current.size,
        'objects'
      );
      console.log('Current mappings:', filamentMappings);

      // Update each object's color based on new mappings
      plateObjectsRef.current.forEach((mesh, name) => {
        // Extract filament index from mesh user data
        const filamentIndex = mesh.userData.filamentIndex || 0;

        console.log(`Object ${name}: filamentIndex=${filamentIndex}`);

        // Get new material with updated color
        const newMaterial = createFilamentMaterial(filamentIndex);

        // Dispose old material
        if (mesh.material && 'dispose' in mesh.material) {
          (mesh.material as THREE.Material).dispose();
        }

        // Apply new material
        mesh.material = newMaterial;
      });

      // Force re-render
      if (rendererRef.current && cameraRef.current) {
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      }
    }, [filamentMappings, amsStatus, createFilamentMaterial]);

    // Load plate-specific geometry when plate changes
    useEffect(() => {
      if (!fileId || !sceneRef.current || !isWebGLAvailable) return;

      const fileExtension = fileId.toLowerCase().split('.').pop();

      // For 3MF files with plates, use Web Worker
      if (fileExtension === '3mf' && plates.length > 0 && workerRef.current) {
        setIsLoading(true);
        setError(null);

        // Fetch the 3MF file
        console.log('Fetching 3MF file with fileId:', fileId);
        fetch(`/api/model/preview/${fileId}`)
          .then(response => {
            if (!response.ok) {
              throw new Error(
                `Failed to fetch file: ${response.status} ${response.statusText}`
              );
            }
            return response.arrayBuffer();
          })
          .then(arrayBuffer => {
            // Parse the specific plate or all plates
            const targetPlate =
              selectedPlateIndex !== null ? selectedPlateIndex : 0;

            workerRef.current!.postMessage({
              type: 'parse',
              fileData: arrayBuffer,
              plateIndex: targetPlate,
            });
          })
          .catch(err => {
            console.error('Failed to fetch 3MF file:', err);
            handleLoadError(err);
          });

        // Handle worker response
        const handleWorkerMessage = (event: MessageEvent) => {
          console.log('Worker message received:', event.data);
          if (event.data.type === 'success') {
            const plateContents = event.data.plateContents as PlateContents;
            console.log('Plate contents:', plateContents);
            currentPlateDataRef.current = plateContents;

            // Clear any existing objects
            sceneRef.current?.children
              .filter(child => child.name.startsWith('plate_group'))
              .forEach(child => {
                sceneRef.current?.remove(child);
                child.traverse(obj => {
                  if ('geometry' in obj) {
                    const mesh = obj as THREE.Mesh;
                    mesh.geometry?.dispose();
                  }
                  if ('material' in obj) {
                    const mesh = obj as THREE.Mesh;
                    if (mesh.material) {
                      if (Array.isArray(mesh.material)) {
                        mesh.material.forEach((m: THREE.Material) =>
                          m?.dispose()
                        );
                      } else {
                        mesh.material.dispose();
                      }
                    }
                  }
                });
              });
            plateObjectsRef.current.clear();

            renderPlateObjects(plateContents);
            setIsLoading(false);
          } else if (event.data.type === 'progress') {
            const progress = event.data.progress;
            if (progress) {
              setLoadingProgress({
                message: progress.message,
                percent: progress.percent,
              });
            }
          } else if (event.data.type === 'error') {
            console.error('Worker error:', event.data.error);
            handleLoadError(new Error(event.data.error));
          }
        };

        workerRef.current.addEventListener('message', handleWorkerMessage);

        return () => {
          workerRef.current?.removeEventListener(
            'message',
            handleWorkerMessage
          );
        };
      } else {
        // Fall back to standard loading for non-plate models
        loadStandardModel();
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
      fileId,
      selectedPlateIndex,
      plates.length, // Only depend on length, not the array itself
      isWebGLAvailable,
    ]);

    // Capture preview method
    const capturePreview = useCallback(async (): Promise<string> => {
      if (!rendererRef.current || !sceneRef.current || !cameraRef.current) {
        throw new Error('Scene not ready for capture');
      }

      // Store current size
      const currentWidth = rendererRef.current.domElement.width;
      const currentHeight = rendererRef.current.domElement.height;

      try {
        // Set to printer display resolution
        const captureWidth = 1280;
        const captureHeight = 720;

        rendererRef.current.setSize(captureWidth, captureHeight);
        cameraRef.current.aspect = captureWidth / captureHeight;
        cameraRef.current.updateProjectionMatrix();

        // Render at capture resolution
        rendererRef.current.render(sceneRef.current, cameraRef.current);

        // Capture as PNG
        const dataURL = rendererRef.current.domElement.toDataURL('image/png');

        return dataURL;
      } finally {
        // Restore original size
        rendererRef.current.setSize(currentWidth, currentHeight);
        cameraRef.current.aspect = currentWidth / currentHeight;
        cameraRef.current.updateProjectionMatrix();
        rendererRef.current.render(sceneRef.current, cameraRef.current);
      }
    }, []);

    // Expose capture method to parent components
    useImperativeHandle(
      ref,
      () => ({
        capturePreview,
      }),
      [capturePreview]
    );

    return (
      <div className={`model-preview-enhanced ${className}`}>
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
          {!isWebGLAvailable && (
            <span className="error-text">
              3D preview unavailable: {initError}
            </span>
          )}
          {isWebGLAvailable && isLoading && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '12px',
                padding: '20px',
                color: '#666',
                fontSize: '14px',
              }}
            >
              <span>{loadingProgress.message}</span>
              <div
                style={{
                  width: '200px',
                  height: '6px',
                  backgroundColor: '#e0e0e0',
                  borderRadius: '3px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${loadingProgress.percent}%`,
                    height: '100%',
                    backgroundColor: '#007bff',
                    borderRadius: '3px',
                    transition: 'width 0.3s ease',
                  }}
                />
              </div>
              <span style={{ fontSize: '12px', color: '#999' }}>
                {Math.round(loadingProgress.percent)}%
              </span>
            </div>
          )}
          {isWebGLAvailable && error && (
            <span className="error-text">{error}</span>
          )}
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
            backgroundColor:
              !isWebGLAvailable || useThumbnail ? '#f5f5f5' : 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {!isWebGLAvailable && (
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

          {isWebGLAvailable && useThumbnail && thumbnailUrl && (
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
                📷{' '}
                {selectedPlateIndex !== null
                  ? `Plate ${selectedPlateIndex} Thumbnail`
                  : 'Model Thumbnail'}
              </div>
            </div>
          )}
        </div>

        {filamentRequirements && filamentRequirements.filament_count > 1 && (
          <div className="preview-note">
            <small>
              🎨 Colors update in real-time as you configure filament mappings.
              {filamentMappings.length <
                filamentRequirements.filament_count && (
                <span> Red objects indicate unmapped filaments.</span>
              )}
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
            </small>
          </div>
        )}
      </div>
    );
  }
);

ModelPreviewEnhanced.displayName = 'ModelPreviewEnhanced';

export default ModelPreviewEnhanced;
