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
  vertexColors?: Float32Array; // RGB colors per vertex (3 floats per vertex)
  isPainted?: boolean; // Flag to indicate if this is a painted model
}

interface PlateContents {
  plateIndex: number;
  objects: PlateObject[];
  projectFilamentColors?: string[];
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
  printerModel?: string; // Add printer model for build volume sizing
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
      printerModel,
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
    const projectColorsRef = useRef<string[] | null>(null);

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

    // State for build volume dimensions fetched from API
    const [buildVolume, setBuildVolume] = useState({
      width: 256,
      depth: 256,
      height: 250,
    });

    // Fetch build volume dimensions from API when printer model changes
    useEffect(() => {
      if (!printerModel) {
        // Use default dimensions if no printer model specified
        setBuildVolume({ width: 256, depth: 256, height: 250 });
        return;
      }

      const fetchBuildVolume = async () => {
        try {
          const response = await fetch(
            `/api/printer/build-volume?printer_model=${encodeURIComponent(printerModel)}`
          );
          const data = await response.json();

          if (data.success && data.width && data.depth && data.height) {
            setBuildVolume({
              width: data.width,
              depth: data.depth,
              height: data.height,
            });
            console.log(
              `Loaded build volume for ${printerModel}: ${data.width}x${data.depth}x${data.height}mm`
            );
          } else {
            console.warn(
              `Failed to load build volume for ${printerModel}: ${data.message}`
            );
            // Keep default dimensions
          }
        } catch (error) {
          console.error(
            `Error fetching build volume for ${printerModel}:`,
            error
          );
          // Keep default dimensions
        }
      };

      fetchBuildVolume();
    }, [printerModel]);

    // Helper function to get filament color from AMS status
    const getFilamentColor = useCallback(
      (filamentIndex: number, projectColors?: string[]): number => {
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

        // Use project filament colors if available (from 3MF project_settings.config)
        if (projectColors && projectColors.length > filamentIndex) {
          const colorStr = projectColors[filamentIndex];
          console.log(
            `Using project color for index ${filamentIndex}: ${colorStr}`
          );
          if (colorStr && colorStr.startsWith('#')) {
            const colorValue = parseInt(colorStr.substring(1), 16);
            console.log(
              `Returning project color: 0x${colorValue.toString(16)}`
            );
            return colorValue;
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
      (
        filamentIndex: number,
        projectColors?: string[],
        isPainted?: boolean
      ): THREE.Material => {
        // For painted models, use vertex colors
        if (isPainted) {
          const material = new THREE.MeshPhongMaterial({
            vertexColors: true, // Enable vertex colors
            side: THREE.DoubleSide,
            shininess: 100,
          });
          material.userData.isPainted = true;
          return material;
        }

        const isMapped = filamentMappings.some(
          m => m.filament_index === filamentIndex
        );
        const color = getFilamentColor(filamentIndex, projectColors);

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

        // Clear model objects from the scene (preserve lights, grid, and build plate)
        const objectsToRemove: THREE.Object3D[] = [];
        sceneRef.current.traverse(child => {
          if (child instanceof THREE.Mesh || child instanceof THREE.Group) {
            if (
              !(child instanceof THREE.Light) &&
              child.name !== 'build_plate_grid' &&
              child.name !== 'build_plate_surface' &&
              child.name !== 'build_plate_border'
            ) {
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

        // Create groups: one for models, one container for everything
        const modelsGroup = new THREE.Group();
        modelsGroup.name = `models_group_${plateContents.plateIndex}`;
        const boundingBox = new THREE.Box3();

        // Store project colors for later use
        projectColorsRef.current = plateContents.projectFilamentColors || null;

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

          // Add vertex colors if this is a painted model
          if (obj.vertexColors && obj.isPainted) {
            geometry.setAttribute(
              'color',
              new THREE.BufferAttribute(obj.vertexColors, 3)
            );
            console.log(`Added vertex colors to object ${obj.id}`);
          }

          // Create material with filament color
          const material = createFilamentMaterial(
            obj.filamentIndex,
            plateContents.projectFilamentColors,
            obj.isPainted // Pass painted flag
          );

          // Create mesh
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = `plate_object_${obj.id}`;
          mesh.userData = {
            filamentIndex: obj.filamentIndex,
            isPainted: obj.isPainted || false,
          };

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

          modelsGroup.add(mesh);
          plateObjectsRef.current.set(mesh.name, mesh);

          // Update bounding box
          geometry.computeBoundingBox();
          if (geometry.boundingBox) {
            boundingBox.expandByObject(mesh);
          }
        });

        // Step 1: Create a container that will hold both models and build plate
        const sceneContainer = new THREE.Group();
        sceneContainer.name = `scene_container_${plateContents.plateIndex}`;

        // Step 2: Add models to container in their original 3MF positions
        if (!boundingBox.isEmpty()) {
          console.log('Original 3MF model bounds:', {
            center: boundingBox.getCenter(new THREE.Vector3()),
            size: boundingBox.getSize(new THREE.Vector3()),
            min: boundingBox.min,
            max: boundingBox.max,
          });

          sceneContainer.add(modelsGroup);

          // Step 3: Create and add build plate at the right position relative to models
          // Position build plate at bed level (Z=0 in 3MF coordinates)
          const center = boundingBox.getCenter(new THREE.Vector3());

          // Create build plate group
          const buildPlateGroup = new THREE.Group();
          buildPlateGroup.name = 'build_plate_group';

          // Create build plate elements (grid, surface, border) at the model's base
          const plateWidth = buildVolume.width;
          const plateDepth = buildVolume.depth;
          const gridSize = Math.max(plateWidth, plateDepth);
          const targetSpacing = 20;
          const gridDivisions = Math.max(
            8,
            Math.floor(gridSize / targetSpacing)
          );

          // Build plate should be positioned at Z=0 (bed level) in 3MF coordinates
          // This way, after rotation, it will be at the bottom of the scene
          const plateZ = 0; // Place build plate at bed level (Z=0 in 3MF coordinates)

          // Grid at bed level - in 3MF coordinates, build plate is XY plane at Z=0
          // GridHelper creates XZ plane grid, so we need to rotate it to XY plane
          const grid = new THREE.GridHelper(
            gridSize,
            gridDivisions,
            0x666666,
            0xcccccc
          );
          grid.rotation.x = Math.PI / 2; // Rotate to make it XY plane in 3MF coordinates
          grid.position.set(center.x, center.y, plateZ); // Position in 3MF: X, Y at Z=0 (bed level)
          buildPlateGroup.add(grid);

          // Build plate surface on XY plane at Z=0 (bed level in 3MF coordinates)
          const plateGeometry = new THREE.PlaneGeometry(plateWidth, plateDepth);
          // PlaneGeometry is already on XY plane, perfect for 3MF coordinates
          const plateMaterial = new THREE.MeshPhongMaterial({
            color: 0xf8f8f8,
            transparent: true,
            opacity: 0.15,
            side: THREE.DoubleSide,
          });
          const buildPlate = new THREE.Mesh(plateGeometry, plateMaterial);
          buildPlate.position.set(center.x, center.y, plateZ - 0.1); // Slightly below grid at bed level
          buildPlate.receiveShadow = true;
          buildPlateGroup.add(buildPlate);

          // Border on XY plane at grid level
          const borderGeometry = new THREE.EdgesGeometry(plateGeometry);
          const borderMaterial = new THREE.LineBasicMaterial({
            color: 0x333333,
            linewidth: 2,
          });
          const buildPlateBorder = new THREE.LineSegments(
            borderGeometry,
            borderMaterial
          );
          buildPlateBorder.position.set(center.x, center.y, plateZ); // Same level as grid at bed level
          buildPlateGroup.add(buildPlateBorder);

          sceneContainer.add(buildPlateGroup);

          // Step 4: Apply global transformations to center and orient the entire scene
          // In 3MF: Z=up, XY=build plate. In final view: Y=up, XZ=build plate
          // Rotate the entire container -90° around X to transform coordinates:
          // 3MF (X,Y,Z) → Final (X,-Z,Y) - this makes Z-up models lay flat on XZ plane
          sceneContainer.rotation.x = -Math.PI / 2;

          // After rotation, get the bounding box and center the entire scene
          sceneContainer.updateMatrixWorld(true);
          const containerBox = new THREE.Box3().setFromObject(sceneContainer);
          const containerCenter = containerBox.getCenter(new THREE.Vector3());
          const containerBottomY = containerBox.min.y;

          // Center the container and place its bottom at Y=0
          sceneContainer.position.set(
            -containerCenter.x, // Center in X
            -containerBottomY, // Bottom at Y=0
            -containerCenter.z // Center in Z
          );

          // Step 5: Add the final container to the scene
          sceneRef.current.add(sceneContainer);
          console.log('Final scene layout:', {
            modelsOriginalBounds: boundingBox,
            buildPlateCenter: { x: center.x, y: plateZ, z: center.z },
            sceneContainerRotation: sceneContainer.rotation,
            sceneContainerPosition: sceneContainer.position,
            finalContainerBounds: containerBox,
            note: 'Models positioned according to 3MF bounds, build plate at Z=0 (bed level), then rotated and centered together',
          });

          // Adjust camera to fit the model properly
          if (
            cameraRef.current &&
            cameraRef.current instanceof THREE.PerspectiveCamera
          ) {
            // Calculate the size of the final scene after rotation and centering
            sceneContainer.updateMatrixWorld(true);
            const finalBox = new THREE.Box3().setFromObject(sceneContainer);
            const finalSize = finalBox.getSize(new THREE.Vector3());
            const maxDimension = Math.max(
              finalSize.x,
              finalSize.y,
              finalSize.z
            );

            // Calculate camera distance to fit the model nicely
            const fov = cameraRef.current.fov * (Math.PI / 180); // Convert to radians
            const cameraDistance = (maxDimension / 2 / Math.tan(fov / 2)) * 1.2; // 1.2 for some padding

            // Position camera so front of build plate is parallel to viewport
            const cameraHeight = cameraDistance * 0.6; // Slightly elevated view
            const cameraX = 0; // Center on X axis
            const cameraZ = cameraDistance; // Position directly in front

            cameraRef.current.position.set(cameraX, cameraHeight, cameraZ);
            cameraRef.current.lookAt(0, 0, 0);
            cameraRef.current.updateProjectionMatrix();

            console.log('Camera positioned for model:', {
              modelSize: finalSize,
              maxDimension,
              cameraDistance,
              cameraPosition: cameraRef.current.position,
            });
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
      [createFilamentMaterial, buildVolume.width, buildVolume.depth]
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
        const height = mount.clientHeight || 500;
        const camera = new THREE.PerspectiveCamera(
          75,
          width / height,
          0.1,
          2000 // Increased far plane to handle very large models
        );
        // Set initial camera position (will be adjusted when model loads)
        const maxBuildDim = Math.max(
          buildVolume.width,
          buildVolume.depth,
          buildVolume.height
        );
        const cameraDistance = maxBuildDim * 1.2; // More reasonable initial distance
        const cameraHeight = maxBuildDim * 0.8;

        camera.position.set(0, cameraHeight, cameraDistance); // Front-facing initial position
        camera.lookAt(0, 0, 0);
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
        controls.minDistance = 5;
        controls.maxDistance = 1000; // Increased from 200 to allow zooming out much further

        // Improved lighting setup for better visibility and stability
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
        scene.add(ambientLight);

        // Main key light from front-right
        const keyLight = new THREE.DirectionalLight(0xffffff, 0.8);
        keyLight.position.set(200, 200, 200);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.width = 2048;
        keyLight.shadow.mapSize.height = 2048;
        keyLight.shadow.camera.near = 0.5;
        keyLight.shadow.camera.far = 1000;
        keyLight.shadow.camera.left = -200;
        keyLight.shadow.camera.right = 200;
        keyLight.shadow.camera.top = 200;
        keyLight.shadow.camera.bottom = -200;
        scene.add(keyLight);

        // Fill light from back-left
        const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
        fillLight.position.set(-100, 150, -100);
        scene.add(fillLight);

        // Additional side light for better form definition
        const sideLight = new THREE.DirectionalLight(0xffffff, 0.2);
        sideLight.position.set(100, 50, -200);
        scene.add(sideLight);

        // Build plate is now created dynamically with each model to maintain proper 3MF layout
        console.log(
          'Three.js scene initialized. Build plate will be created with models.',
          'Printer model:',
          printerModel,
          'Build volume:',
          buildVolume
        );

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
          const newHeight = mount.clientHeight || 500;

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
    }, [buildVolume, printerModel]);

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

        // Get new material with updated color, using stored project colors
        const newMaterial = createFilamentMaterial(
          filamentIndex,
          projectColorsRef.current,
          mesh.userData.isPainted
        );

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

      // For 3MF files, use Web Worker to parse and render with paint colors
      if (fileExtension === '3mf' && workerRef.current) {
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
            height: '500px',
            aspectRatio: '1',
            maxWidth: '500px',
            margin: '0 auto',
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
                  maxHeight: '460px',
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
