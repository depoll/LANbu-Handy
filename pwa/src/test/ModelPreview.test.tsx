import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import ModelPreview from '../components/ModelPreview';
import { FilamentRequirement, FilamentMapping } from '../types/api';

// Mock Three.js
vi.mock('three', () => ({
  Scene: vi.fn(() => ({
    background: {},
    add: vi.fn(),
    remove: vi.fn(),
  })),
  PerspectiveCamera: vi.fn(() => ({
    position: { set: vi.fn() },
    aspect: 0,
    updateProjectionMatrix: vi.fn(),
  })),
  WebGLRenderer: vi.fn(() => ({
    setSize: vi.fn(),
    shadowMap: { enabled: false, type: {} },
    domElement: document.createElement('canvas'),
    render: vi.fn(),
    dispose: vi.fn(),
  })),
  AmbientLight: vi.fn(),
  DirectionalLight: vi.fn(() => ({
    position: { set: vi.fn() },
    castShadow: false,
  })),
  MeshLambertMaterial: vi.fn(() => ({
    color: { setHex: vi.fn() },
  })),
  Mesh: vi.fn(() => ({
    castShadow: false,
    receiveShadow: false,
    scale: { setScalar: vi.fn() },
    rotation: { y: 0 },
    material: { color: { setHex: vi.fn() } },
  })),
  Color: vi.fn(),
  Vector3: vi.fn(() => ({
    set: vi.fn(),
  })),
  PCFSoftShadowMap: {},
}));

vi.mock('three-stdlib', () => ({
  STLLoader: vi.fn(() => ({
    load: vi.fn((url, onLoad) => {
      // Mock successful loading
      const mockGeometry = {
        computeBoundingBox: vi.fn(),
        boundingBox: {
          getCenter: vi.fn(() => ({ x: 0, y: 0, z: 0 })),
          getSize: vi.fn(() => ({ x: 10, y: 10, z: 10 })),
        },
        translate: vi.fn(),
      };
      setTimeout(() => onLoad(mockGeometry), 100);
    }),
  })),
}));

// Mock requestAnimationFrame and cancelAnimationFrame
Object.defineProperty(window, 'requestAnimationFrame', {
  writable: true,
  value: vi.fn((cb) => setTimeout(cb, 16)),
});

Object.defineProperty(window, 'cancelAnimationFrame', {
  writable: true,
  value: vi.fn(),
});

describe('ModelPreview Component', () => {
  let mockFilamentRequirements: FilamentRequirement;
  let mockFilamentMappings: FilamentMapping[];

  beforeEach(() => {
    mockFilamentRequirements = {
      filament_count: 2,
      filament_types: ['PLA', 'PETG'],
      filament_colors: ['#ff0000', '#00ff00'],
      has_multicolor: true,
    };

    mockFilamentMappings = [
      { filament_index: 0, ams_unit_id: 0, ams_slot_id: 0 },
      { filament_index: 1, ams_unit_id: 0, ams_slot_id: 1 },
    ];
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<ModelPreview fileId="test-file.stl" />);
    
    expect(screen.getByText('Model Preview')).toBeInTheDocument();
  });

  it('shows loading state initially', () => {
    render(<ModelPreview fileId="test-file.stl" />);
    
    expect(screen.getByText('Loading model...')).toBeInTheDocument();
  });

  it('renders preview container with correct dimensions', () => {
    render(<ModelPreview fileId="test-file.stl" />);
    
    const container = document.querySelector('.model-preview-container');
    expect(container).toBeInTheDocument();
    expect(container).toHaveStyle({ 
      width: '100%', 
      height: '300px' 
    });
  });

  it('shows multi-material warning for multicolor models', () => {
    render(
      <ModelPreview
        fileId="test-file.3mf"
        filamentRequirements={mockFilamentRequirements}
        filamentMappings={mockFilamentMappings}
      />
    );

    expect(
      screen.getByText(/Multi-material models show simplified color preview/)
    ).toBeInTheDocument();
  });

  it('does not show multi-material warning for single color models', () => {
    const singleColorRequirements: FilamentRequirement = {
      filament_count: 1,
      filament_types: ['PLA'],
      filament_colors: ['#ff0000'],
      has_multicolor: false,
    };

    render(
      <ModelPreview
        fileId="test-file.stl"
        filamentRequirements={singleColorRequirements}
        filamentMappings={[mockFilamentMappings[0]]}
      />
    );

    expect(
      screen.queryByText(/Multi-material models show simplified color preview/)
    ).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(
      <ModelPreview
        fileId="test-file.stl"
        className="custom-preview-class"
      />
    );

    const previewDiv = document.querySelector('.model-preview');
    expect(previewDiv).toHaveClass('custom-preview-class');
  });

  it('handles file ID changes', () => {
    const { rerender } = render(<ModelPreview fileId="file1.stl" />);
    
    expect(screen.getByText('Loading model...')).toBeInTheDocument();

    rerender(<ModelPreview fileId="file2.stl" />);
    
    // Should still show loading for the new file
    expect(screen.getByText('Loading model...')).toBeInTheDocument();
  });

  it('handles empty filament mappings', () => {
    render(
      <ModelPreview
        fileId="test-file.stl"
        filamentRequirements={mockFilamentRequirements}
        filamentMappings={[]}
      />
    );

    // Should render without errors even with empty mappings
    expect(screen.getByText('Model Preview')).toBeInTheDocument();
  });

  it('handles missing filament requirements', () => {
    render(
      <ModelPreview
        fileId="test-file.stl"
        filamentMappings={mockFilamentMappings}
      />
    );

    // Should render without errors even without filament requirements
    expect(screen.getByText('Model Preview')).toBeInTheDocument();
    expect(
      screen.queryByText(/Multi-material models show simplified color preview/)
    ).not.toBeInTheDocument();
  });
});