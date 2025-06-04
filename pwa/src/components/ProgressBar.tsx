interface ProgressBarProps {
  value?: number; // 0-100 for determinate, undefined for indeterminate
  label?: string;
  showPercentage?: boolean;
  size?: 'small' | 'medium' | 'large';
  color?: 'primary' | 'success' | 'warning' | 'error';
  className?: string;
}

function ProgressBar({
  value,
  label,
  showPercentage = false,
  size = 'medium',
  color = 'primary',
  className = '',
}: ProgressBarProps) {
  const isIndeterminate = value === undefined;
  const percentage = isIndeterminate ? 0 : Math.min(100, Math.max(0, value));

  return (
    <div className={`progress-bar-container ${className}`}>
      {label && (
        <div className="progress-bar-header">
          <span className="progress-bar-label">{label}</span>
          {showPercentage && !isIndeterminate && (
            <span className="progress-bar-percentage">{percentage}%</span>
          )}
        </div>
      )}
      <div
        className={`progress-bar progress-bar-${size} progress-bar-${color}`}
      >
        <div
          className={`progress-bar-fill ${isIndeterminate ? 'progress-bar-indeterminate' : ''}`}
          style={
            isIndeterminate
              ? undefined
              : {
                  width: `${percentage}%`,
                }
          }
        />
      </div>
    </div>
  );
}

export default ProgressBar;
