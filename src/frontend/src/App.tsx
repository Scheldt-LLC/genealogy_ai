import { useState, useEffect } from 'react'
import './App.css'
import Upload from './components/Upload'
import Chat from './components/Chat'
import Tree from './components/Tree'

interface HealthResponse {
  status: string
  service: string
  version: string
}

type Tab = 'upload' | 'chat' | 'tree'

function App() {
  const [apiStatus, setApiStatus] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('upload')

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

      <nav className="app-nav">
        <button
          className={`nav-tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          Upload Documents
        </button>
        <button
          className={`nav-tab ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </button>
        <button
          className={`nav-tab ${activeTab === 'tree' ? 'active' : ''}`}
          onClick={() => setActiveTab('tree')}
        >
          Family Tree
        </button>
      </nav>

      <main>
        {activeTab === 'upload' && <Upload />}
        {activeTab === 'chat' && <Chat />}
        {activeTab === 'tree' && <Tree />}
      </main>
    </>
  )
}

export default App
