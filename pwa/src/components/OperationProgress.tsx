import ProgressBar from './ProgressBar';

export interface OperationStep {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress?: number; // 0-100 for running steps
  message?: string;
  details?: string;
}

interface OperationProgressProps {
  title: string;
  steps: OperationStep[];
  className?: string;
}

function OperationProgress({ title, steps, className = '' }: OperationProgressProps) {
  const completedSteps = steps.filter(step => step.status === 'completed').length;
  const totalSteps = steps.length;
  const overallProgress = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;

  const getStepIcon = (step: OperationStep) => {
    switch (step.status) {
      case 'completed':
        return '✅';
      case 'error':
        return '❌';
      case 'running':
        return '⏳';
      case 'pending':
      default:
        return '⭕';
    }
  };

  const getStepStatusClass = (step: OperationStep) => {
    switch (step.status) {
      case 'completed':
        return 'operation-step-completed';
      case 'error':
        return 'operation-step-error';
      case 'running':
        return 'operation-step-running';
      case 'pending':
      default:
        return 'operation-step-pending';
    }
  };

  return (
    <div className={`operation-progress ${className}`}>
      <div className="operation-progress-header">
        <h4 className="operation-progress-title">{title}</h4>
        <div className="operation-progress-summary">
          {completedSteps} of {totalSteps} steps completed
        </div>
      </div>

      <ProgressBar
        value={overallProgress}
        showPercentage={false}
        size="medium"
        color={steps.some(s => s.status === 'error') ? 'error' : 'primary'}
        className="operation-progress-bar"
      />

      <div className="operation-steps">
        {steps.map((step, index) => (
          <div key={step.id} className={`operation-step ${getStepStatusClass(step)}`}>
            <div className="operation-step-header">
              <div className="operation-step-indicator">
                <span className="operation-step-icon">{getStepIcon(step)}</span>
                <span className="operation-step-number">{index + 1}</span>
              </div>
              <div className="operation-step-content">
                <div className="operation-step-label">{step.label}</div>
                {step.message && (
                  <div className="operation-step-message">{step.message}</div>
                )}
                {step.details && (
                  <div className="operation-step-details">{step.details}</div>
                )}
              </div>
            </div>
            {step.status === 'running' && step.progress !== undefined && (
              <ProgressBar
                value={step.progress}
                showPercentage={true}
                size="small"
                color="primary"
                className="operation-step-progress"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default OperationProgress;