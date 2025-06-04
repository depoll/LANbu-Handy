import { FilamentRequirement } from '../types/api';

interface FilamentRequirementsDisplayProps {
  requirements: FilamentRequirement;
  className?: string;
}

function FilamentRequirementsDisplay({
  requirements,
  className = '',
}: FilamentRequirementsDisplayProps) {
  const renderFilamentInfo = () => {
    const { filament_count, filament_types, filament_colors } = requirements;

    if (filament_count === 0) {
      return (
        <div className="no-requirements">No specific filament requirements</div>
      );
    }

    const filamentItems = [];
    for (let i = 0; i < filament_count; i++) {
      const type = filament_types[i] || 'Unknown';
      const color = filament_colors[i] || 'Unknown';

      filamentItems.push(
        <div key={i} className="filament-requirement">
          <div className="requirement-index">Filament {i + 1}:</div>
          <div className="requirement-details">
            <span className="requirement-type">{type}</span>
            <div className="requirement-color">
              {color.startsWith('#') ? (
                <div className="color-info">
                  <div
                    className="color-swatch"
                    style={{ backgroundColor: color }}
                    title={color}
                  ></div>
                  <span className="color-label">{color}</span>
                </div>
              ) : (
                <span className="color-name">{color}</span>
              )}
            </div>
          </div>
        </div>
      );
    }

    return filamentItems;
  };

  return (
    <div className={`filament-requirements-display ${className}`}>
      <div className="requirements-header">
        <h3>Model Filament Requirements</h3>
        <div className="requirements-summary">
          {requirements.filament_count > 0 ? (
            <span className="requirement-count">
              {requirements.filament_count} filament
              {requirements.filament_count !== 1 ? 's' : ''} required
              {requirements.has_multicolor && (
                <span className="multicolor-badge">Multi-color</span>
              )}
            </span>
          ) : (
            <span className="no-count">No specific requirements</span>
          )}
        </div>
      </div>

      <div className="requirements-content">{renderFilamentInfo()}</div>
    </div>
  );
}

export default FilamentRequirementsDisplay;
