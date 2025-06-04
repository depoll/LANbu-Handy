import { useEffect, useState } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import Features from './components/Features';
import SliceAndPrint from './components/SliceAndPrint';
import Footer from './components/Footer';
import { ToastProvider } from './components/ToastProvider';
import './App.css';

interface AppStatus {
  status: 'initializing' | 'ready' | 'error';
  message?: string;
  backendData?: {
    status: string;
    application_name: string;
    version: string;
  };
}

function App() {
  const [appStatus, setAppStatus] = useState<AppStatus>({
    status: 'initializing',
  });

  useEffect(() => {
    // Initialize the app
    console.log('LANbu Handy PWA initializing...');

    // Register service worker for PWA functionality (future implementation)
    if ('serviceWorker' in navigator) {
      console.log('Service worker support detected');
    }

    // Fetch backend status
    const fetchBackendStatus = async () => {
      try {
        console.log('Fetching backend status...');
        const response = await fetch('/api/status');

        // Check if response exists and is valid
        if (!response) {
          throw new Error('No response received from server');
        }

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const backendData = await response.json();
        console.log('Backend status received:', backendData);

        // Set app as ready with backend data
        setAppStatus({
          status: 'ready',
          backendData,
          message: 'Connected to backend successfully',
        });
        console.log('LANbu Handy PWA ready');
      } catch (error) {
        console.error('Failed to fetch backend status:', error);
        setAppStatus({
          status: 'error',
          message: `Failed to connect to backend: ${error instanceof Error ? error.message : 'Unknown error'}`,
        });
      }
    };

    fetchBackendStatus();
  }, []);

  const handleFeatureClick = (featureName: string) => {
    console.log('Feature card clicked:', featureName);
  };

  return (
    <ToastProvider>
      <div className={`app ${appStatus.status === 'ready' ? 'app-ready' : ''}`}>
        <Header />

        {/* Backend Status Display */}
        <div className="status-bar">
          {appStatus.status === 'initializing' && (
            <div className="status-message status-loading">
              Connecting to backend...
            </div>
          )}

          {appStatus.status === 'ready' && appStatus.backendData && (
            <div className="status-message status-success">
              ✓ {appStatus.backendData.application_name} v
              {appStatus.backendData.version} - Status:{' '}
              {appStatus.backendData.status}
            </div>
          )}

          {appStatus.status === 'error' && (
            <div className="status-message status-error">
              ⚠ {appStatus.message}
            </div>
          )}
        </div>

        <main>
          <Hero />
          <SliceAndPrint />
          <Features onFeatureClick={handleFeatureClick} />
        </main>
        <Footer />
      </div>
    </ToastProvider>
  );
}

export default App;
