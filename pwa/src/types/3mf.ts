// Types for 3MF file parsing

export interface Vertex3MF {
  '@_x'?: number;
  '@_y'?: number;
  '@_z'?: number;
}

export interface Triangle3MF {
  '@_v1': number;
  '@_v2': number;
  '@_v3': number;
  '@_pid'?: number;
  '@_p1'?: number;
  '@_p2'?: number;
  '@_p3'?: number;
}

export interface TriangleColor3MF {
  '@_vf1'?: number;
  '@_vf2'?: number;
  '@_vf3'?: number;
}

export interface Mesh3MF {
  vertices?: {
    vertex?: Vertex3MF | Vertex3MF[];
  };
  triangles?: {
    triangle?: Triangle3MF | Triangle3MF[];
  };
  trianglecolors?: {
    color?: TriangleColor3MF | TriangleColor3MF[];
  };
}

export interface Transform3MF {
  '@_m00'?: number;
  '@_m01'?: number;
  '@_m02'?: number;
  '@_m10'?: number;
  '@_m11'?: number;
  '@_m12'?: number;
  '@_m20'?: number;
  '@_m21'?: number;
  '@_m22'?: number;
  '@_m30'?: number;
  '@_m31'?: number;
  '@_m32'?: number;
}

export interface Object3MF {
  '@_id': string;
  '@_type'?: string;
  mesh?: Mesh3MF;
  components?: {
    component?: Component3MF | Component3MF[];
  };
}

export interface Component3MF {
  '@_objectid': string;
  '@_transform'?: string;
  '@_p:path'?: string;
}

export interface Item3MF {
  '@_objectid': string;
  '@_transform'?: string;
}

export interface Build3MF {
  item?: Item3MF | Item3MF[];
}

export interface Resources3MF {
  object?: Object3MF | Object3MF[];
}

export interface Model3MF {
  model?: {
    resources?: Resources3MF;
    build?: Build3MF;
  };
}

export interface ResourceTexture2D {
  '@_id': string;
  '@_path': string;
  '@_contenttype': string;
}

export interface Color3MF {
  '@_color': string;
}

export interface ColorGroup3MF {
  '@_id': string;
  colors?: {
    color?: Color3MF | Color3MF[];
  };
}

export interface TexCoord3MF {
  '@_u': number;
  '@_v': number;
}

export interface Texture2DGroup3MF {
  '@_id': string;
  '@_texid': string;
  texcoord?: TexCoord3MF | TexCoord3MF[];
}

export interface Triangle2D3MF {
  '@_v1': number;
  '@_v2': number;
  '@_v3': number;
  '@_texid': string;
  '@_tv1': number;
  '@_tv2': number;
  '@_tv3': number;
}

export interface PlateObject {
  id: string;
  type: 'normal' | 'component' | 'painted';
  vertices: Float32Array;
  indices: Uint32Array;
  transform: Float32Array;
  filamentColors: Record<number, string>;
  paintedTriangles?: Array<{
    indices: Uint32Array;
    filamentIndex: number;
  }>;
}

export interface ParsedPlateData {
  index: number;
  name: string;
  filaments: string[];
  objects: PlateObject[];
  thumbnail?: string;
  displayName?: string;
  objectCount?: number;
}

export interface TextureData {
  width: number;
  height: number;
  filamentData: number[];
  primaryFilamentIndex: number;
}

export interface TriangleRegion {
  vertices: { u: number; v: number }[];
  filament: number;
  pixelCount: number;
}

export interface TriangleSubdivision {
  triangle: Triangle3MF;
  filamentIndex: number;
  newVertices?: Vertex3MF[];
}
