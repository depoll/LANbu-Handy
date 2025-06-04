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
  // Common Bambu Lab build plate types
  const buildPlateOptions = [
    { value: 'auto', label: 'Auto (Use Model Default)' },
    { value: 'cool_plate', label: 'Cool Plate' },
    { value: 'engineering_plate', label: 'Engineering Plate' },
    { value: 'high_temp_plate', label: 'High Temp Plate' },
    { value: 'textured_pei_plate', label: 'Textured PEI Plate' },
    { value: 'smooth_pei_plate', label: 'Smooth PEI Plate' },
  ];

  return (
    <div className="build-plate-selector">
      <div className="selector-header">
        <h4>Build Plate Type</h4>
        <p>Select the build plate currently installed on your printer</p>
      </div>

      <div className="plate-selection">
        <label htmlFor="build-plate-select">Build Plate:</label>
        <select
          id="build-plate-select"
          value={selectedPlate}
          onChange={e => onPlateSelect(e.target.value)}
          disabled={disabled}
          className="build-plate-select"
        >
          {buildPlateOptions.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default BuildPlateSelector;
