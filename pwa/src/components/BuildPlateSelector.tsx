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
  // Common Bambu Lab build plate types with actual thumbnail images
  const buildPlateOptions = [
    {
      value: 'textured_pei_plate',
      label: 'Textured PEI',
      image: '/api/resources/images/bed_pei.png',
      description: 'Best for most prints',
    },
    {
      value: 'hot_plate',
      label: 'Smooth PEI',
      image: '/api/resources/images/bed_high_templ.png',
      description: 'Smooth bottom finish',
    },
    {
      value: 'cool_plate',
      label: 'Cool Plate',
      image: '/api/resources/images/bed_cool.png',
      description: 'For delicate materials',
    },
    {
      value: 'engineering_plate',
      label: 'Engineering',
      image: '/api/resources/images/bed_engineering.png',
      description: 'High-temp materials',
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
              <img
                src={option.image}
                alt={option.label}
                className="plate-thumbnail-image"
              />
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
