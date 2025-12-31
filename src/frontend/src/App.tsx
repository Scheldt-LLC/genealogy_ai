import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

interface HealthResponse {
  status: string
  service: string
  version: string
}

function App() {
  const [count, setCount] = useState(0)
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
      <div>
        <a href="https://vite.dev" target="_blank">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <h1>Genealogy AI</h1>

      {/* API Status */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3>Backend Status</h3>
        {apiStatus ? (
          <p style={{ color: 'green' }}>
            ✓ Connected to {apiStatus.service} v{apiStatus.version}
          </p>
        ) : error ? (
          <p style={{ color: 'red' }}>✗ Error: {error}</p>
        ) : (
          <p>Connecting...</p>
        )}
      </div>

      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </button>
        <p>
          Edit <code>src/App.tsx</code> and save to test HMR
        </p>
      </div>
      <p className="read-the-docs">
        Frontend + Backend connected and ready to build! 🚀
      </p>
    </>
  )
}

export default App
