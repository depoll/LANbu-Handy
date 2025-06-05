import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { STLLoader } from 'three-stdlib';
import { FilamentRequirement, FilamentMapping } from '../types/api';

interface ModelPreviewProps {
  fileId: string;
  filamentRequirements?: FilamentRequirement;
  filamentMappings?: FilamentMapping[];
  className?: string;
}

const ModelPreview: React.FC<ModelPreviewProps> = ({
  fileId,
  filamentRequirements,
  filamentMappings = [],
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

  // Initialize Three.js scene
  useEffect(() => {
    if (!mountRef.current) return;

    const container = mountRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight || 300;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf5f5f5);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 0, 50);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;

    container.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(1, 1, 1);
    directionalLight.castShadow = true;
    scene.add(directionalLight);

    // Controls (simple rotation animation)
    const animate = () => {
      if (meshRef.current) {
        meshRef.current.rotation.y += 0.005;
      }
      renderer.render(scene, camera);
      animationRef.current = requestAnimationFrame(animate);
    };
    animate();

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
      window.removeEventListener('resize', handleResize);
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  // Load model
  useEffect(() => {
    if (!fileId || !sceneRef.current) return;

    setIsLoading(true);
    setError(null);

    const loader = new STLLoader();
    const modelUrl = `/api/model/preview/${fileId}`;

    loader.load(
      modelUrl,
      (geometry) => {
        // Remove existing mesh
        if (meshRef.current) {
          sceneRef.current?.remove(meshRef.current);
        }

        // Create material with default color
        const material = new THREE.MeshLambertMaterial({ 
          color: getModelColor(0, filamentRequirements, filamentMappings)
        });

        // Create mesh
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        meshRef.current = mesh;

        // Center and scale the model
        geometry.computeBoundingBox();
        const box = geometry.boundingBox!;
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        
        // Center the geometry
        geometry.translate(-center.x, -center.y, -center.z);
        
        // Scale to fit in view
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = 30 / maxDim;
        mesh.scale.setScalar(scale);

        sceneRef.current!.add(mesh);
        setIsLoading(false);
      },
      (progress) => {
        // Loading progress
        console.log('Model loading progress:', progress);
      },
      (error) => {
        console.error('Error loading model:', error);
        setError('Failed to load model for preview');
        setIsLoading(false);
      }
    );
  }, [fileId, filamentRequirements, filamentMappings]);

  // Update colors when filament mappings change
  useEffect(() => {
    if (!meshRef.current || !filamentRequirements) return;

    const newColor = getModelColor(0, filamentRequirements, filamentMappings);
    (meshRef.current.material as THREE.MeshLambertMaterial).color.setHex(newColor);
  }, [filamentMappings, filamentRequirements]);

  return (
    <div className={`model-preview ${className}`}>
      <div className="model-preview-header">
        <h3>Model Preview</h3>
        {isLoading && <span className="loading-text">Loading model...</span>}
        {error && <span className="error-text">{error}</span>}
      </div>
      <div 
        ref={mountRef} 
        className="model-preview-container"
        style={{ 
          width: '100%', 
          height: '300px', 
          border: '1px solid #ddd',
          borderRadius: '8px',
          overflow: 'hidden'
        }}
      />
      {filamentRequirements && filamentRequirements.filament_count > 1 && (
        <div className="preview-note">
          <small>
            ⚠️ Multi-material models show simplified color preview. 
            Actual print will use mapped filament colors.
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
    const mapping = filamentMappings.find(m => m.filament_index === filamentIndex);
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
  if (filamentRequirements && filamentRequirements.filament_colors.length > filamentIndex) {
    const colorStr = filamentRequirements.filament_colors[filamentIndex];
    if (colorStr && colorStr.startsWith('#')) {
      return parseInt(colorStr.substring(1), 16);
    }
  }

  // Default to a neutral color
  return 0x888888;
}

export default ModelPreview;