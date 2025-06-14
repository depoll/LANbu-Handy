import { useState, useEffect } from 'react';
import { AMSStatusResponse } from '../types/api';

interface AMSStatusDisplayProps {
  printerId: string;
  onStatusUpdate?: (status: AMSStatusResponse) => void;
}

// Check if a color represents an empty slot
function isEmptyColor(hex: string): boolean {
  // Handle empty or invalid color values
  if (
    !hex ||
    hex === '' ||
    hex === '#' ||
    hex === '00000000' ||
    hex === '#00000000'
  ) {
    return true;
  }

  return false;
}

// Check if a color is transparent (has alpha = 0 but has actual color data)
function isTransparentColor(hex: string): boolean {
  if (!hex) return false;

  // Remove # if present
  let cleanHex = hex.replace('#', '');

  // Handle 8-character hex (RGBA) - check for fully transparent
  if (cleanHex.length === 8) {
    const alpha = cleanHex.substring(6, 8);
    const colorPart = cleanHex.substring(0, 6);
    // If alpha is 00 but there's actual color data (not all zeros), it's transparent
    if (alpha === '00' && colorPart !== '000000') {
      return true;
    }
  }

  return false;
}

// Convert hex color to approximate named color
function getApproximateColorName(hex: string): string {
  // Remove # if present
  let cleanHex = hex.replace('#', '');

  // Handle 8-character hex (RGBA) by removing alpha channel
  if (cleanHex.length === 8) {
    cleanHex = cleanHex.substring(0, 6);
  }

  // Ensure we have a valid 6-character hex
  if (cleanHex.length !== 6) {
    return 'Unknown';
  }

  // Convert to RGB
  const r = parseInt(cleanHex.substring(0, 2), 16);
  const g = parseInt(cleanHex.substring(2, 4), 16);
  const b = parseInt(cleanHex.substring(4, 6), 16);

  // Define common colors with their RGB values
  const colors: Array<{ name: string; r: number; g: number; b: number }> = [
    // Blacks and Whites
    { name: 'Black', r: 0, g: 0, b: 0 },
    { name: 'Jet Black', r: 52, g: 52, b: 52 },
    { name: 'Charcoal', r: 54, g: 69, b: 79 },
    { name: 'White', r: 255, g: 255, b: 255 },
    { name: 'Off White', r: 248, g: 248, b: 255 },
    { name: 'Ivory', r: 255, g: 255, b: 240 },
    { name: 'Cream', r: 255, g: 253, b: 208 },
    { name: 'Pearl', r: 234, g: 234, b: 234 },

    // Grays
    { name: 'Light Gray', r: 211, g: 211, b: 211 },
    { name: 'Silver', r: 192, g: 192, b: 192 },
    { name: 'Gray', r: 128, g: 128, b: 128 },
    { name: 'Dark Gray', r: 64, g: 64, b: 64 },
    { name: 'Slate Gray', r: 112, g: 128, b: 144 },
    { name: 'Gunmetal', r: 42, g: 52, b: 57 },

    // Reds
    { name: 'Red', r: 255, g: 0, b: 0 },
    { name: 'Bright Red', r: 255, g: 0, b: 0 },
    { name: 'Dark Red', r: 139, g: 0, b: 0 },
    { name: 'Crimson', r: 220, g: 20, b: 60 },
    { name: 'Cherry Red', r: 222, g: 49, b: 99 },
    { name: 'Burgundy', r: 128, g: 0, b: 32 },
    { name: 'Maroon', r: 128, g: 0, b: 0 },
    { name: 'Brick Red', r: 203, g: 65, b: 84 },
    { name: 'Fire Engine Red', r: 206, g: 32, b: 41 },
    { name: 'Rose Red', r: 194, g: 30, b: 86 },

    // Pinks
    { name: 'Pink', r: 255, g: 192, b: 203 },
    { name: 'Hot Pink', r: 255, g: 105, b: 180 },
    { name: 'Deep Pink', r: 255, g: 20, b: 147 },
    { name: 'Light Pink', r: 255, g: 182, b: 193 },
    { name: 'Fuchsia', r: 255, g: 0, b: 255 },
    { name: 'Magenta', r: 255, g: 0, b: 255 },
    { name: 'Rose', r: 255, g: 0, b: 127 },
    { name: 'Coral', r: 255, g: 127, b: 80 },
    { name: 'Salmon', r: 250, g: 128, b: 114 },
    { name: 'Peach', r: 255, g: 218, b: 185 },

    // Oranges
    { name: 'Orange', r: 255, g: 165, b: 0 },
    { name: 'Dark Orange', r: 255, g: 140, b: 0 },
    { name: 'Bright Orange', r: 255, g: 165, b: 0 },
    { name: 'Burnt Orange', r: 204, g: 85, b: 0 },
    { name: 'Tangerine', r: 242, g: 133, b: 0 },
    { name: 'Pumpkin Orange', r: 255, g: 117, b: 24 },
    { name: 'Safety Orange', r: 255, g: 102, b: 0 },
    { name: 'Amber', r: 255, g: 191, b: 0 },

    // Yellows
    { name: 'Yellow', r: 255, g: 255, b: 0 },
    { name: 'Bright Yellow', r: 255, g: 255, b: 0 },
    { name: 'Lemon Yellow', r: 255, g: 244, b: 79 },
    { name: 'Golden Yellow', r: 255, g: 223, b: 0 },
    { name: 'Canary Yellow', r: 255, g: 239, b: 0 },
    { name: 'Gold', r: 255, g: 215, b: 0 },
    { name: 'Dark Gold', r: 184, g: 134, b: 11 },
    { name: 'Mustard Yellow', r: 255, g: 219, b: 88 },
    { name: 'Beige', r: 245, g: 245, b: 220 },
    { name: 'Tan', r: 210, g: 180, b: 140 },

    // Greens
    { name: 'Green', r: 0, g: 255, b: 0 },
    { name: 'Bright Green', r: 0, g: 255, b: 0 },
    { name: 'Lime Green', r: 50, g: 205, b: 50 },
    { name: 'Forest Green', r: 34, g: 139, b: 34 },
    { name: 'Hunter Green', r: 63, g: 142, b: 67 },
    { name: 'Dark Green', r: 0, g: 128, b: 0 },
    { name: 'Emerald Green', r: 80, g: 200, b: 120 },
    { name: 'Kelly Green', r: 76, g: 187, b: 23 },
    { name: 'Olive Green', r: 128, g: 128, b: 0 },
    { name: 'Army Green', r: 75, g: 83, b: 32 },
    { name: 'Sage Green', r: 158, g: 169, b: 157 },
    { name: 'Mint Green', r: 152, g: 255, b: 152 },
    { name: 'Sea Green', r: 46, g: 139, b: 87 },
    { name: 'Pine Green', r: 1, g: 121, b: 111 },
    { name: 'Jungle Green', r: 41, g: 171, b: 135 },

    // Blues
    { name: 'Blue', r: 0, g: 0, b: 255 },
    { name: 'Bright Blue', r: 0, g: 0, b: 255 },
    { name: 'Sky Blue', r: 135, g: 206, b: 235 },
    { name: 'Light Blue', r: 173, g: 216, b: 230 },
    { name: 'Royal Blue', r: 65, g: 105, b: 225 },
    { name: 'Navy Blue', r: 0, g: 0, b: 128 },
    { name: 'Dark Blue', r: 0, g: 0, b: 139 },
    { name: 'Midnight Blue', r: 25, g: 25, b: 112 },
    { name: 'Steel Blue', r: 70, g: 130, b: 180 },
    { name: 'Powder Blue', r: 176, g: 224, b: 230 },
    { name: 'Cornflower Blue', r: 100, g: 149, b: 237 },
    { name: 'Electric Blue', r: 0, g: 191, b: 255 },
    { name: 'Cobalt Blue', r: 0, g: 71, b: 171 },
    { name: 'Prussian Blue', r: 0, g: 49, b: 83 },

    // Cyans and Teals
    { name: 'Cyan', r: 0, g: 255, b: 255 },
    { name: 'Aqua', r: 0, g: 255, b: 255 },
    { name: 'Turquoise', r: 64, g: 224, b: 208 },
    { name: 'Teal', r: 0, g: 128, b: 128 },
    { name: 'Dark Teal', r: 0, g: 64, b: 64 },
    { name: 'Light Teal', r: 128, g: 208, b: 208 },
    { name: 'Seafoam', r: 159, g: 226, b: 191 },

    // Purples
    { name: 'Purple', r: 128, g: 0, b: 128 },
    { name: 'Violet', r: 238, g: 130, b: 238 },
    { name: 'Dark Purple', r: 72, g: 61, b: 139 },
    { name: 'Light Purple', r: 221, g: 160, b: 221 },
    { name: 'Royal Purple', r: 120, g: 81, b: 169 },
    { name: 'Lavender', r: 230, g: 230, b: 250 },
    { name: 'Orchid', r: 218, g: 112, b: 214 },
    { name: 'Plum', r: 221, g: 160, b: 221 },
    { name: 'Indigo', r: 75, g: 0, b: 130 },
    { name: 'Deep Purple', r: 102, g: 51, b: 153 },
    { name: 'Amethyst', r: 153, g: 102, b: 204 },

    // Browns
    { name: 'Brown', r: 165, g: 42, b: 42 },
    { name: 'Dark Brown', r: 101, g: 67, b: 33 },
    { name: 'Light Brown', r: 181, g: 101, b: 29 },
    { name: 'Chocolate Brown', r: 123, g: 63, b: 0 },
    { name: 'Coffee Brown', r: 111, g: 78, b: 55 },
    { name: 'Mocha', r: 112, g: 66, b: 20 },
    { name: 'Chestnut', r: 149, g: 69, b: 53 },
    { name: 'Mahogany', r: 192, g: 64, b: 0 },
    { name: 'Copper', r: 184, g: 115, b: 51 },
    { name: 'Bronze', r: 205, g: 127, b: 50 },

    // Special Colors
    { name: 'Transparent', r: 128, g: 128, b: 128 }, // Default for transparent materials
    { name: 'Clear', r: 240, g: 248, b: 255 },
    { name: 'Translucent White', r: 245, g: 245, b: 245 },
    { name: 'Natural', r: 245, g: 245, b: 220 },
    { name: 'Wood Tone', r: 210, g: 180, b: 140 },
    { name: 'Metallic Silver', r: 192, g: 192, b: 192 },
    { name: 'Metallic Gold', r: 255, g: 215, b: 0 },
    { name: 'Neon Green', r: 57, g: 255, b: 20 },
    { name: 'Neon Pink', r: 255, g: 16, b: 240 },
    { name: 'Neon Blue', r: 77, g: 77, b: 255 },
    { name: 'Neon Yellow', r: 255, g: 255, b: 51 },
    { name: 'Glow in Dark', r: 192, g: 255, b: 192 },
  ];

  // Find the closest color
  let closestColor = 'Unknown';
  let minDistance = Infinity;

  for (const color of colors) {
    // Calculate Euclidean distance in RGB space
    const distance = Math.sqrt(
      Math.pow(r - color.r, 2) +
        Math.pow(g - color.g, 2) +
        Math.pow(b - color.b, 2)
    );

    if (distance < minDistance) {
      minDistance = distance;
      closestColor = color.name;
    }
  }

  return closestColor;
}

function AMSStatusDisplay({
  printerId,
  onStatusUpdate,
}: AMSStatusDisplayProps) {
  const [amsStatus, setAmsStatus] = useState<AMSStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAMSStatus = async () => {
    if (!printerId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/printer/${printerId}/ams-status`);

      // Check if response exists and is valid
      if (!response) {
        throw new Error('No response received from server');
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const status: AMSStatusResponse = await response.json();
      setAmsStatus(status);

      if (onStatusUpdate) {
        onStatusUpdate(status);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Unknown error occurred';
      setError(`Failed to fetch AMS status: ${errorMessage}`);
      console.error('AMS status fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAMSStatus();
  }, [printerId]); // eslint-disable-line react-hooks/exhaustive-deps

  const renderFilamentSlot = (filament: {
    slot_id: number;
    filament_type: string;
    color: string;
    material_id?: string;
  }) => {
    // Check if this is an empty slot or transparent
    const isEmpty = isEmptyColor(filament.color);
    const isTransparent = isTransparentColor(filament.color);

    // Convert color hex codes to a readable format or use the raw value
    const colorDisplay = filament.color.startsWith('#')
      ? filament.color
      : filament.color;

    // Get approximate color name if it's a hex value
    let colorName = filament.color.startsWith('#')
      ? getApproximateColorName(filament.color)
      : filament.color;

    // Override with "Transparent" for transparent colors
    if (isTransparent) {
      colorName = 'Transparent';
    }

    return (
      <div key={filament.slot_id} className="filament-slot">
        <div className="slot-header">
          <span className="slot-id">Slot {filament.slot_id}</span>
          <span className="filament-type">{filament.filament_type}</span>
        </div>
        <div className="filament-details">
          {!isEmpty && (
            <div className="color-info">
              <div
                className="color-swatch"
                style={{
                  backgroundColor: isTransparent
                    ? 'rgba(240, 240, 240, 0.5)'
                    : colorDisplay,
                  border: isTransparent
                    ? '2px dashed rgba(128, 128, 128, 0.5)'
                    : undefined,
                }}
                title={filament.color}
              ></div>
              <div className="color-labels">
                <span className="color-name">{colorName}</span>
                <span className="color-hex">{filament.color}</span>
              </div>
            </div>
          )}
          {isEmpty && (
            <div className="empty-slot-info">
              <span className="empty-indicator">No filament loaded</span>
            </div>
          )}
          {filament.material_id && (
            <div className="material-id">Material: {filament.material_id}</div>
          )}
        </div>
      </div>
    );
  };

  const renderAMSUnit = (unit: {
    unit_id: number;
    filaments: Array<{
      slot_id: number;
      filament_type: string;
      color: string;
      material_id?: string;
    }>;
  }) => {
    return (
      <div key={unit.unit_id} className="ams-unit">
        <h4>AMS Unit {unit.unit_id}</h4>
        <div className="filament-slots">
          {unit.filaments.length > 0 ? (
            unit.filaments.map(renderFilamentSlot)
          ) : (
            <div className="no-filaments">No filaments loaded</div>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="ams-status-display">
        <div className="status-header">
          <h3>AMS Status</h3>
          <button onClick={fetchAMSStatus} disabled className="refresh-button">
            Loading...
          </button>
        </div>
        <div className="workflow-loading">
          <div className="loading-spinner"></div>
          <span className="loading-text">
            Fetching AMS status from printer...
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ams-status-display">
        <div className="status-header">
          <h3>AMS Status</h3>
          <button onClick={fetchAMSStatus} className="refresh-button">
            Retry
          </button>
        </div>
        <div className="error">⚠ {error}</div>
      </div>
    );
  }

  if (!amsStatus) {
    return (
      <div className="ams-status-display">
        <div className="status-header">
          <h3>AMS Status</h3>
          <button onClick={fetchAMSStatus} className="refresh-button">
            Load AMS Status
          </button>
        </div>
        <div className="no-data">No AMS status available</div>
      </div>
    );
  }

  return (
    <div className="ams-status-display">
      <div className="status-header">
        <h3>AMS Status</h3>
        <button onClick={fetchAMSStatus} className="refresh-button">
          Refresh
        </button>
      </div>

      {amsStatus.success ? (
        <div className="ams-content">
          <div className="status-message">✓ {amsStatus.message}</div>
          {amsStatus.ams_units && amsStatus.ams_units.length > 0 ? (
            <div className="ams-units">
              {amsStatus.ams_units.map(renderAMSUnit)}
            </div>
          ) : (
            <div className="no-ams">No AMS units found</div>
          )}
        </div>
      ) : (
        <div className="ams-error">
          <div className="error-message">❌ {amsStatus.message}</div>
          {amsStatus.error_details && (
            <div className="error-details">
              Details: {amsStatus.error_details}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AMSStatusDisplay;
