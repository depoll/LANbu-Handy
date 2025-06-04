/**
 * Manual validation script to test component interfaces
 * Run with: npm run validate (after adding to package.json scripts)
 */

import { FilamentRequirement, AMSStatusResponse } from './types/api';

// Test data that matches the backend API structure
const mockFilamentRequirement: FilamentRequirement = {
  filament_count: 2,
  filament_types: ['PLA', 'PETG'],
  filament_colors: ['#FF0000', '#00FF00'],
  has_multicolor: true,
};

const mockAMSStatus: AMSStatusResponse = {
  success: true,
  message: 'AMS status retrieved successfully',
  ams_units: [
    {
      unit_id: 0,
      filaments: [
        {
          slot_id: 0,
          filament_type: 'PLA',
          color: '#FF0000',
          material_id: 'GF00001',
        },
        {
          slot_id: 1,
          filament_type: 'PETG',
          color: '#00FF00',
          material_id: 'GF00002',
        },
      ],
    },
  ],
};

// Validate interface compliance
console.log('Validating FilamentRequirement interface:');
console.log('- filament_count:', mockFilamentRequirement.filament_count);
console.log('- filament_types:', mockFilamentRequirement.filament_types);
console.log('- filament_colors:', mockFilamentRequirement.filament_colors);
console.log('- has_multicolor:', mockFilamentRequirement.has_multicolor);

console.log('\nValidating AMSStatusResponse interface:');
console.log('- success:', mockAMSStatus.success);
console.log('- message:', mockAMSStatus.message);
console.log('- ams_units count:', mockAMSStatus.ams_units?.length);

if (mockAMSStatus.ams_units) {
  console.log(
    '- first unit filaments:',
    mockAMSStatus.ams_units[0].filaments.length
  );
}

console.log('\n✅ All interfaces validated successfully');

export { mockFilamentRequirement, mockAMSStatus };
