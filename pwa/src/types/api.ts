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
