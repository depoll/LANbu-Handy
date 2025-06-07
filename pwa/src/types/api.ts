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

// Model Filament Requirements and Plate Types
export interface PlateInfo {
  index: number;
  prediction_seconds?: number;
  weight_grams?: number;
  has_support: boolean;
  object_count: number;
}

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
  plates?: PlateInfo[];
  has_multiple_plates: boolean;
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
  selected_plate_index?: number | null; // null means all plates
}

export interface SliceResponse {
  success: boolean;
  message: string;
  gcode_path?: string;
  error_details?: string;
}

// Printer Configuration Types
export interface SetActivePrinterRequest {
  ip: string;
  access_code?: string;
  name?: string;
  serial_number?: string;
}

export interface SetActivePrinterResponse {
  success: boolean;
  message: string;
  printer_info?: {
    name: string;
    ip: string;
    has_access_code: boolean;
    has_serial_number: boolean;
  };
  error_details?: string;
}

export interface PrinterConfigResponse {
  printer_configured: boolean;
  printers: {
    name: string;
    ip: string;
    has_access_code: boolean;
    has_serial_number: boolean;
    is_persistent?: boolean;
    source?: 'persistent' | 'environment';
  }[];
  printer_count: number;
  persistent_printer_count?: number;
  active_printer?: {
    name: string;
    ip: string;
    has_access_code: boolean;
    has_serial_number: boolean;
    is_runtime_set: boolean;
    is_persistent?: boolean;
  };
  printer_ip?: string; // Legacy field
}

// New Persistent Printer Management Types
export interface AddPrinterRequest {
  ip: string;
  access_code?: string;
  name?: string;
  serial_number?: string;
}

export interface AddPrinterResponse {
  success: boolean;
  message: string;
  printer_info?: {
    name: string;
    ip: string;
    has_access_code: boolean;
    has_serial_number: boolean;
    is_persistent: boolean;
  };
  error_details?: string;
}

export interface RemovePrinterRequest {
  ip: string;
}

export interface RemovePrinterResponse {
  success: boolean;
  message: string;
  error_details?: string;
}

export interface PersistentPrintersResponse {
  success: boolean;
  message: string;
  printers?: {
    name: string;
    ip: string;
    has_access_code: boolean;
    has_serial_number: boolean;
    is_persistent: boolean;
  }[];
  error_details?: string;
}

// Filament Matching API Types
export interface FilamentMatchRequest {
  filament_requirements: FilamentRequirement;
  ams_status: AMSStatusResponse;
}

export interface FilamentMatchResult {
  requirement_index: number;
  ams_unit_id: number;
  ams_slot_id: number;
  match_quality: string; // "perfect", "type_only", "fallback", "none"
  confidence: number;
}

export interface FilamentMatchResponse {
  success: boolean;
  message: string;
  matches?: FilamentMatchResult[];
  unmatched_requirements?: number[];
  error_details?: string;
}
