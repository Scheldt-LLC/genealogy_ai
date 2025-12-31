import { useState, useEffect, useRef, DragEvent, ChangeEvent } from 'react'
import './Upload.css'

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

export default function Upload() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
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

  // Load documents on mount
  useEffect(() => {
    fetchDocuments()
  }, [])

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
    const file = files[0]
    setError(null)
    setSuccess(null)
    setUploading(true)

    const formData = new FormData()
    formData.append('file', file)

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

        setSuccess(`${data.filename} processed successfully! (${stats.join(', ')})`)
        // Refresh document list
        await fetchDocuments()
      } else {
        setError((data as any).error || 'Upload failed')
      }
    } catch (err) {
      setError('Failed to upload file: ' + (err as Error).message)
    } finally {
      setUploading(false)
    }
  }

  const onButtonClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="upload-container">
      <h2>Upload Documents</h2>

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
              <p>Drag and drop a file here, or click to select</p>
              <p className="upload-hint">
                Supported: PDF, PNG, JPG, TIFF, BMP, TXT
              </p>
            </>
          )}
        </div>
      </div>

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
        <h3>Uploaded Documents ({documents.length})</h3>
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
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
