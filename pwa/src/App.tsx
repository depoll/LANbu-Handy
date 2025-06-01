import { useEffect, useState } from 'react'
import Header from './components/Header'
import Hero from './components/Hero'
import Features from './components/Features'
import Footer from './components/Footer'
import './App.css'

interface AppStatus {
  status: 'initializing' | 'ready' | 'error'
  message?: string
}

function App() {
  const [appStatus, setAppStatus] = useState<AppStatus>({ status: 'initializing' })
  
  useEffect(() => {
    // Initialize the app
    console.log('LANbu Handy PWA initializing...')
    
    // Register service worker for PWA functionality (future implementation)
    if ('serviceWorker' in navigator) {
      console.log('Service worker support detected')
    }
    
    // Set app as ready
    setAppStatus({ status: 'ready' })
    console.log('LANbu Handy PWA ready')
  }, [])

  const handleFeatureClick = (featureName: string) => {
    console.log('Feature card clicked:', featureName)
  }

  return (
    <div className={`app ${appStatus.status === 'ready' ? 'app-ready' : ''}`}>
      <Header />
      <main>
        <Hero />
        <Features onFeatureClick={handleFeatureClick} />
      </main>
      <Footer />
    </div>
  )
}

export default App
