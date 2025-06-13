interface BuildPlateSelectorProps {
  selectedPlate: string;
  onPlateSelect: (plateType: string) => void;
  disabled?: boolean;
}

function BuildPlateSelector({
  selectedPlate,
  onPlateSelect,
  disabled = false,
}: BuildPlateSelectorProps) {
  // Common Bambu Lab build plate types (removed auto option)
  const buildPlateOptions = [
    { 
      value: 'textured_pei_plate', 
      label: 'Textured PEI', 
      icon: '🔹',
      description: 'Best for most prints' 
    },
    { 
      value: 'smooth_pei_plate', 
      label: 'Smooth PEI', 
      icon: '⚪',
      description: 'Smooth bottom finish' 
    },
    { 
      value: 'cool_plate', 
      label: 'Cool Plate', 
      icon: '❄️',
      description: 'For delicate materials' 
    },
    { 
      value: 'engineering_plate', 
      label: 'Engineering', 
      icon: '🔧',
      description: 'High-temp materials' 
    },
  ];

  return (
    <div className="build-plate-selector">
      <div className="selector-header">
        <h4>Build Plate Type</h4>
        <p>Select the build plate currently installed on your printer</p>
      </div>

      <div className="build-plate-grid">
        {buildPlateOptions.map(option => (
          <div
            key={option.value}
            className={`build-plate-option ${
              selectedPlate === option.value ? 'selected' : ''
            }`}
            onClick={() => !disabled && onPlateSelect(option.value)}
            style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}
          >
            <div className="plate-visual">
              <span className="plate-icon">{option.icon}</span>
            </div>
            <div className="plate-info">
              <div className="plate-name">{option.label}</div>
              <div className="plate-description">{option.description}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default BuildPlateSelector;
