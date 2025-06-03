import { useState } from 'react'

interface JobStep {
  success: boolean
  message: string
  details: string
}

interface JobResponse {
  success: boolean
  message: string
  job_steps?: {
    download: JobStep
    slice: JobStep
    upload: JobStep
    print: JobStep
  }
  error_details?: string
}

function SliceAndPrint() {
  const [modelUrl, setModelUrl] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [statusMessages, setStatusMessages] = useState<string[]>([])

  const addStatusMessage = (message: string) => {
    setStatusMessages(prev => [...prev, `${new Date().toLocaleTimeString()}: ${message}`])
  }

  const handleSliceAndPrint = async () => {
    if (!modelUrl.trim()) {
      addStatusMessage('Error: Please enter a model URL')
      return
    }

    setIsProcessing(true)
    setStatusMessages([])
    addStatusMessage('Starting slice and print workflow...')

    try {
      const requestBody = { model_url: modelUrl.trim() }
      
      addStatusMessage('Sending request to backend...')
      const response = await fetch('/api/job/start-basic', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorText}`)
      }

      const result: JobResponse = await response.json()
      
      // Display main result
      if (result.success) {
        addStatusMessage(`✅ ${result.message}`)
      } else {
        addStatusMessage(`❌ ${result.message}`)
        if (result.error_details) {
          addStatusMessage(`Details: ${result.error_details}`)
        }
      }

      // Display step-by-step progress if available
      if (result.job_steps) {
        const steps = ['download', 'slice', 'upload', 'print'] as const
        
        for (const stepName of steps) {
          const step = result.job_steps[stepName]
          if (step && step.message) {
            const status = step.success ? '✅' : '❌'
            addStatusMessage(`${status} ${stepName.charAt(0).toUpperCase() + stepName.slice(1)}: ${step.message}`)
            if (step.details && step.details !== step.message) {
              addStatusMessage(`   Details: ${step.details}`)
            }
          }
        }
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
      addStatusMessage(`❌ Error: ${errorMessage}`)
      console.error('Slice and print error:', error)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isProcessing) {
      handleSliceAndPrint()
    }
  }

  return (
    <div className="slice-and-print">
      <div className="slice-and-print-header">
        <h2>Slice and Print</h2>
        <p>Enter a URL to your 3D model file (.stl or .3mf) to slice and print with default settings</p>
      </div>

      <div className="slice-and-print-form">
        <div className="input-group">
          <label htmlFor="model-url">Model URL:</label>
          <input
            id="model-url"
            type="url"
            value={modelUrl}
            onChange={(e) => setModelUrl(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="https://example.com/model.stl"
            disabled={isProcessing}
            className="model-url-input"
          />
        </div>
        
        <button
          onClick={handleSliceAndPrint}
          disabled={isProcessing || !modelUrl.trim()}
          className="slice-and-print-button"
        >
          {isProcessing ? 'Processing...' : 'Slice and Print with Defaults'}
        </button>
      </div>

      {statusMessages.length > 0 && (
        <div className="status-display">
          <h3>Status:</h3>
          <div className="status-messages">
            {statusMessages.map((message, index) => (
              <div key={index} className="status-message">
                {message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default SliceAndPrint