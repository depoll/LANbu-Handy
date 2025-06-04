/**
 * TypeScript interfaces for LANbu Handy API responses
 */

// AMS Status API Types
export interface AMSFilament {
  slot_id: number;
  filament_type: string;
  color: string;
  material_id?: string;
}

export interface AMSUnit {
  unit_id: number;
  filaments: AMSFilament[];
}

export interface AMSStatusResponse {
  success: boolean;
  message: string;
  ams_units?: AMSUnit[];
  error_details?: string;
}

// Model Filament Requirements Types
export interface FilamentRequirement {
  filament_count: number;
  filament_types: string[];
  filament_colors: string[];
  has_multicolor: boolean;
}

export interface ModelSubmissionResponse {
  success: boolean;
  message: string;
  file_id?: string;
  file_info?: Record<string, unknown>;
  filament_requirements?: FilamentRequirement;
}

// Filament Mapping and Configuration Types
export interface FilamentMapping {
  filament_index: number; // Index in the model's filament requirements
  ams_unit_id: number;
  ams_slot_id: number;
}

export interface ConfiguredSliceRequest {
  file_id: string;
  filament_mappings: FilamentMapping[];
  build_plate_type: string;
}

export interface SliceResponse {
  success: boolean;
  message: string;
  gcode_path?: string;
  error_details?: string;
}
