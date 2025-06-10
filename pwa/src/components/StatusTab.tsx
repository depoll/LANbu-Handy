import AMSStatusDisplay from './AMSStatusDisplay';
import OperationProgress, { OperationStep } from './OperationProgress';
import { AMSStatusResponse } from '../types/api';

interface StatusTabProps {
  printerId: string;
  onAMSStatusUpdate: (status: AMSStatusResponse) => void;
  operationSteps: OperationStep[];
  showOperationProgress: boolean;
  statusMessages: string[];
}

export function StatusTab({
  printerId,
  onAMSStatusUpdate,
  operationSteps,
  showOperationProgress,
  statusMessages,
}: StatusTabProps) {
  return (
    <div className="status-tab">
      <div className="status-header">
        <h3>System Status</h3>
        <p>
          Monitor your printer status, AMS filaments, and operation progress
        </p>
      </div>

      {/* AMS Status Display - Always available */}
      <div className="status-section">
        <AMSStatusDisplay
          printerId={printerId}
          onStatusUpdate={onAMSStatusUpdate}
        />
      </div>

      {/* Enhanced Operation Progress */}
      {showOperationProgress && operationSteps.length > 0 && (
        <div className="status-section">
          <OperationProgress
            title="Current Operation"
            steps={operationSteps}
            className="workflow-section"
          />
        </div>
      )}

      {/* Status Messages */}
      {statusMessages.length > 0 && (
        <div className="status-section">
          <div className="status-display">
            <h4>System Log</h4>
            <div className="status-messages">
              {statusMessages.map((message, index) => (
                <div key={index} className="status-message">
                  {message}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Empty state when no status messages */}
      {statusMessages.length === 0 && (
        <div className="status-section">
          <div className="status-placeholder">
            <div className="placeholder-icon">📊</div>
            <h4>System Log</h4>
            <p>Status messages will appear here as operations are performed.</p>
          </div>
        </div>
      )}
    </div>
  );
}
