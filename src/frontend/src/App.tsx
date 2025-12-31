import { useState, useEffect } from 'react'
import './App.css'
import Upload from './components/Upload'

interface HealthResponse {
  status: string
  service: string
  version: string
}

function App() {
  const [apiStatus, setApiStatus] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Test API connection
    fetch('/api/health')
      .then((res) => res.json())
      .then((data: HealthResponse) => setApiStatus(data))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <>
      <header className="app-header">
        <h1>Genealogy AI</h1>
        <div className="status">
          {apiStatus ? (
            <span style={{ color: 'green' }}>
              ✓ Connected to {apiStatus.service}
            </span>
          ) : error ? (
            <span style={{ color: 'red' }}>✗ {error}</span>
          ) : (
            <span>Connecting...</span>
          )}
        </div>
      </header>

      <main>
        <Upload />
      </main>
    </>
  )
}

export default App
