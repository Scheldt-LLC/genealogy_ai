import { useState, useEffect, useRef, DragEvent, ChangeEvent } from 'react'
import './Upload.css'
import DocumentDetails from './DocumentDetails'

interface Document {
  id: number
  filename: string
  file_path: string
  page_count: number
  created_at: string | null
}

interface UploadResponse {
  success: boolean
  document_ids: number[]
  filename: string
  page_count: number
  entities_extracted: {
    people: number
    events: number
    relationships: number
  }
  duplicates_merged: number
  chunks_stored: number
  message: string
}

interface FileProgress {
  name: string
  status: 'pending' | 'uploading' | 'success' | 'error'
  message?: string
}

export default function Upload() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [uploadQueue, setUploadQueue] = useState<FileProgress[]>([])
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null)
  const [ocrEngine, setOcrEngine] = useState<'tesseract' | 'azure'>('tesseract')
  const [azureKey, setAzureKey] = useState('')
  const [azureEndpoint, setAzureEndpoint] = useState('')
  const [saveToSession, setSaveToSession] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [isAzureConfiguredOnServer, setIsAzureConfiguredOnServer] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchDocuments = async () => {
    try {
      const response = await fetch('/api/documents')
      const data = await response.json()
      if (data.success) {
        setDocuments(data.documents)
      }
    } catch (err) {
      console.error('Failed to fetch documents:', err)
    }
  }

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/config')
      const data = await response.json()
      setIsAzureConfiguredOnServer(data.azure_configured)
    } catch (err) {
      console.error('Failed to fetch config:', err)
    }
  }

  // Load documents and session settings on mount
  useEffect(() => {
    fetchDocuments()
    fetchConfig()

    const savedKey = sessionStorage.getItem('azure_key')
    const savedEndpoint = sessionStorage.getItem('azure_endpoint')
    if (savedKey) setAzureKey(savedKey)
    if (savedEndpoint) setAzureEndpoint(savedEndpoint)
    if (savedKey || savedEndpoint) setSaveToSession(true)
  }, [])

  // Update session storage when settings change
  useEffect(() => {
    if (saveToSession) {
      sessionStorage.setItem('azure_key', azureKey)
      sessionStorage.setItem('azure_endpoint', azureEndpoint)
    } else {
      sessionStorage.removeItem('azure_key')
      sessionStorage.removeItem('azure_endpoint')
    }
  }, [azureKey, azureEndpoint, saveToSession])

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files)
    }
  }

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      handleFiles(e.target.files)
    }
  }

  const handleFiles = async (files: FileList) => {
    const fileArray = Array.from(files)

    if (fileArray.length === 0) return

    setError(null)
    setSuccess(null)
    setUploading(true)

    // Initialize progress tracking for all files
    const initialProgress: FileProgress[] = fileArray.map(file => ({
      name: file.name,
      status: 'pending',
    }))
    setUploadQueue(initialProgress)

    let successCount = 0
    let errorCount = 0

    // Process files sequentially to avoid overwhelming the server
    for (let i = 0; i < fileArray.length; i++) {
      const file = fileArray[i]

      // Update status to uploading
      setUploadQueue(prev => prev.map((item, idx) =>
        idx === i ? { ...item, status: 'uploading' } : item
      ))

      const formData = new FormData()
      formData.append('file', file)
      formData.append('engine', ocrEngine)
      
      // Add Azure credentials if using Azure engine
      if (ocrEngine === 'azure') {
        if (azureKey) formData.append('azure_key', azureKey)
        if (azureEndpoint) formData.append('azure_endpoint', azureEndpoint)
      }

      // Add OpenAI key from session storage if available
      const sessionOpenAIKey = sessionStorage.getItem('openai_api_key')
      if (sessionOpenAIKey) {
        formData.append('openai_key', sessionOpenAIKey)
      }

      try {
        const response = await fetch('/api/upload', {
          method: 'POST',
          body: formData,
        })

        const data: UploadResponse = await response.json()

        if (response.ok && data.success) {
          const stats = []
          stats.push(`${data.page_count} page${data.page_count !== 1 ? 's' : ''}`)
          if (data.entities_extracted.people > 0) {
            stats.push(`${data.entities_extracted.people} people`)
          }
          if (data.entities_extracted.events > 0) {
            stats.push(`${data.entities_extracted.events} events`)
          }
          if (data.duplicates_merged > 0) {
            stats.push(`${data.duplicates_merged} duplicate${data.duplicates_merged !== 1 ? 's' : ''} merged`)
          }

          // Update status to success
          setUploadQueue(prev => prev.map((item, idx) =>
            idx === i ? {
              ...item,
              status: 'success',
              message: stats.join(', ')
            } : item
          ))
          successCount++
        } else {
          // Update status to error
          setUploadQueue(prev => prev.map((item, idx) =>
            idx === i ? {
              ...item,
              status: 'error',
              message: (data as any).error || 'Upload failed'
            } : item
          ))
          errorCount++
        }
      } catch (err) {
        // Update status to error
        setUploadQueue(prev => prev.map((item, idx) =>
          idx === i ? {
            ...item,
            status: 'error',
            message: (err as Error).message
          } : item
        ))
        errorCount++
      }
    }

    // Refresh document list after all uploads
    await fetchDocuments()
    setUploading(false)

    // Set final success/error message
    if (errorCount === 0) {
      setSuccess(`Successfully uploaded ${successCount} file${successCount !== 1 ? 's' : ''}!`)
    } else if (successCount === 0) {
      setError(`Failed to upload all ${errorCount} file${errorCount !== 1 ? 's' : ''}`)
    } else {
      setSuccess(`Uploaded ${successCount} file${successCount !== 1 ? 's' : ''}, ${errorCount} failed`)
    }

    // Clear queue after a delay
    setTimeout(() => setUploadQueue([]), 5000)
  }

  const onButtonClick = () => {
    fileInputRef.current?.click()
  }

  const handleDelete = async (documentId: number) => {
    if (!window.confirm('Are you sure you want to delete this document? This will remove all extracted entities.')) {
      return
    }

    setDeleting(documentId)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch(`/api/documents/${documentId}`, {
        method: 'DELETE',
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setSuccess('Document deleted successfully')
        await fetchDocuments()
      } else {
        setError(data.error || 'Failed to delete document')
      }
    } catch (err) {
      setError('Failed to delete document: ' + (err as Error).message)
    } finally {
      setDeleting(null)
    }
  }

  const handleReset = async () => {
    if (!window.confirm('Are you sure you want to RESET THE ENTIRE DATABASE? This will delete ALL documents and extracted data. This action cannot be undone!')) {
      return
    }

    // Double confirmation
    if (!window.confirm('This is your last chance! Click OK to permanently delete everything.')) {
      return
    }

    setUploading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch('/api/reset', {
        method: 'POST',
      })

      const data = await response.json()

      if (response.ok && data.success) {
        setSuccess('Database reset successfully. All data has been deleted.')
        await fetchDocuments()
      } else {
        setError(data.error || 'Failed to reset database')
      }
    } catch (err) {
      setError('Failed to reset database: ' + (err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="upload-container">
      <h2>Upload Documents</h2>

      {/* OCR Engine Selection */}
      <div className="ocr-settings">
        <div className="engine-toggle">
          <label>
            <input
              type="radio"
              name="engine"
              value="tesseract"
              checked={ocrEngine === 'tesseract'}
              onChange={() => setOcrEngine('tesseract')}
            />
            Standard OCR (Free)
          </label>
          <label>
            <input
              type="radio"
              name="engine"
              value="azure"
              checked={ocrEngine === 'azure'}
              onChange={() => setOcrEngine('azure')}
            />
            Advanced OCR (Azure AI)
          </label>
        </div>

        {ocrEngine === 'azure' && (
          <div className="azure-credentials">
            {!isAzureConfiguredOnServer ? (
              <>
                <button 
                  type="button" 
                  className="advanced-toggle"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  {showAdvanced ? 'Hide' : 'Show'} Azure Credentials
                </button>
                
                {showAdvanced && (
                  <div className="credentials-form">
                    <div className="form-group">
                      <label htmlFor="azureKey">API Key:</label>
                      <input
                        id="azureKey"
                        type="password"
                        value={azureKey}
                        onChange={(e) => setAzureKey(e.target.value)}
                        placeholder="Enter Azure AI Document Intelligence Key"
                      />
                    </div>
                    <div className="form-group">
                      <label htmlFor="azureEndpoint">Endpoint:</label>
                      <input
                        id="azureEndpoint"
                        type="text"
                        value={azureEndpoint}
                        onChange={(e) => setAzureEndpoint(e.target.value)}
                        placeholder="https://your-resource.cognitiveservices.azure.com/"
                      />
                    </div>
                    <div className="form-group checkbox-group">
                      <label>
                        <input
                          type="checkbox"
                          checked={saveToSession}
                          onChange={(e) => setSaveToSession(e.target.checked)}
                        />
                        Save to session (wiped when tab closes)
                      </label>
                    </div>
                    <p className="credential-hint">
                      Leave blank to use server-side environment variables.
                    </p>
                  </div>
                )}
              </>
            ) : (
              <p className="credential-status success">
                ✅ Azure AI is configured on the server.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Upload Area */}
      <div
        className={`upload-area ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={onButtonClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="file-input"
          onChange={handleChange}
          accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.txt"
          multiple
        />
        <div className="upload-content">
          {uploading ? (
            <>
              <p className="upload-icon">⚙️</p>
              <p>Processing document...</p>
              <p className="upload-hint">
                Running OCR, extracting entities, and building family tree
              </p>
            </>
          ) : (
            <>
              <p className="upload-icon">📁</p>
              <p>Drag and drop files here, or click to select</p>
              <p className="upload-hint">
                Supported: PDF, PNG, JPG, TIFF, BMP, TXT • Multiple files OK
              </p>
            </>
          )}
        </div>
      </div>

      {/* Upload Queue Progress */}
      {uploadQueue.length > 0 && (
        <div className="upload-queue">
          <h4>Upload Progress</h4>
          <div className="queue-list">
            {uploadQueue.map((file, idx) => (
              <div key={idx} className={`queue-item queue-item-${file.status}`}>
                <div className="queue-icon">
                  {file.status === 'pending' && '⏳'}
                  {file.status === 'uploading' && '⚙️'}
                  {file.status === 'success' && '✅'}
                  {file.status === 'error' && '❌'}
                </div>
                <div className="queue-info">
                  <div className="queue-filename">{file.name}</div>
                  {file.message && (
                    <div className="queue-message">{file.message}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Status Messages */}
      {error && (
        <div className="message error">
          <strong>Error:</strong> {error}
        </div>
      )}
      {success && (
        <div className="message success">
          <strong>Success:</strong> {success}
        </div>
      )}

      {/* Documents List */}
      <div className="documents-section">
        <div className="documents-header">
          <h3>Uploaded Documents ({documents.length})</h3>
          {documents.length > 0 && (
            <button
              className="reset-button"
              onClick={handleReset}
              disabled={uploading}
            >
              🗑️ Reset Database
            </button>
          )}
        </div>
        {documents.length === 0 ? (
          <p className="no-documents">No documents uploaded yet.</p>
        ) : (
          <div className="documents-list">
            {documents.map((doc) => (
              <div key={doc.id} className="document-card">
                <div className="document-info">
                  <div className="document-name">{doc.filename}</div>
                  <span className="document-meta">
                    {doc.page_count} page{doc.page_count !== 1 ? 's' : ''}
                    {doc.created_at && (
                      <> • {new Date(doc.created_at).toLocaleDateString()}</>
                    )}
                  </span>
                </div>
                <div className="document-actions">
                  <button
                    className="details-button"
                    onClick={() => setSelectedDocumentId(doc.id)}
                    title="View extracted text"
                  >
                    📄
                  </button>
                  <a
                    href={`/api/documents/${doc.id}/file`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="view-button"
                    title="View original file"
                  >
                    👁️
                  </a>
                  <button
                    className="delete-button"
                    onClick={() => handleDelete(doc.id)}
                    disabled={deleting === doc.id}
                    title="Delete document"
                  >
                    {deleting === doc.id ? '⏳' : '🗑️'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Document Details Modal */}
      {selectedDocumentId && (
        <DocumentDetails
          documentId={selectedDocumentId}
          onClose={() => setSelectedDocumentId(null)}
        />
      )}
    </div>
  )
}
