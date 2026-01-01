import { useEffect, useState } from 'react'
import './DocumentDetails.css'

interface PageData {
  page: number
  ocr_text: string
}

interface DocumentDetailsData {
  success: boolean
  document_id: number
  filename: string
  source: string
  page_count: number
  created_at: string
  pages: PageData[]
}

interface DocumentDetailsProps {
  documentId: number
  onClose: () => void
}

export default function DocumentDetails({ documentId, onClose }: DocumentDetailsProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [details, setDetails] = useState<DocumentDetailsData | null>(null)
  const [editing, setEditing] = useState(false)
  const [editedPages, setEditedPages] = useState<PageData[]>([])
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        const response = await fetch(`/api/documents/${documentId}/details`)
        const data = await response.json()

        if (response.ok && data.success) {
          setDetails(data)
        } else {
          setError(data.error || 'Failed to load document details')
        }
      } catch (err) {
        setError('Failed to load document details: ' + (err as Error).message)
      } finally {
        setLoading(false)
      }
    }

    fetchDetails()
  }, [documentId])

  const handleEdit = () => {
    if (details) {
      setEditedPages([...details.pages])
      setEditing(true)
    }
  }

  const handleCancelEdit = () => {
    setEditing(false)
    setEditedPages([])
    setSaveSuccess(false)
  }

  const handlePageTextChange = (pageIndex: number, newText: string) => {
    setEditedPages((prev) =>
      prev.map((page, idx) =>
        idx === pageIndex ? { ...page, ocr_text: newText } : page
      )
    )
  }

  const handleSave = async () => {
    if (!details) return

    setSaving(true)
    setError(null)
    setSaveSuccess(false)

    try {
      const response = await fetch(`/api/documents/${documentId}/update-text`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          pages: editedPages,
        }),
      })

      const data = await response.json()

      if (response.ok && data.success) {
        // Update the details with the new text
        setDetails({ ...details, pages: editedPages })
        setEditing(false)
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
      } else {
        setError(data.error || 'Failed to save changes')
      }
    } catch (err) {
      setError('Failed to save changes: ' + (err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Document Details</h2>
          <button className="modal-close" onClick={onClose} title="Close">
            ✕
          </button>
        </div>

        {loading ? (
          <div className="modal-loading">
            <p>Loading document details...</p>
          </div>
        ) : error ? (
          <div className="modal-error">
            <strong>Error:</strong> {error}
          </div>
        ) : details ? (
          <div className="modal-body">
            <div className="document-info-header">
              <div className="info-item">
                <strong>Filename:</strong> {details.filename}
              </div>
              <div className="info-item">
                <strong>Pages:</strong> {details.page_count}
              </div>
              {details.created_at && (
                <div className="info-item">
                  <strong>Uploaded:</strong> {new Date(details.created_at).toLocaleString()}
                </div>
              )}
            </div>

            <div className="split-view-container">
              {/* Left side - Original Document */}
              <div className="document-viewer-pane">
                <h3>Original Document</h3>
                <div className="document-viewer">
                  <iframe
                    src={`/api/documents/${documentId}/file`}
                    title="Original Document"
                    className="document-iframe"
                  />
                </div>
              </div>

              {/* Right side - OCR Text */}
              <div className="ocr-content-pane">
                <div className="ocr-header">
                  <h3>Extracted Text (OCR)</h3>
                  {!editing && (
                    <button className="edit-button" onClick={handleEdit}>
                      ✏️ Edit
                    </button>
                  )}
                </div>
                {saveSuccess && (
                  <div className="save-success">
                    Changes saved successfully! Vector embeddings updated.
                  </div>
                )}
                <div className="ocr-content-scrollable">
                  {(editing ? editedPages : details.pages).map((page, idx) => (
                    <div key={page.page} className="page-section">
                      <div className="page-header">
                        Page {page.page}
                      </div>
                      <div className="page-text">
                        {page.ocr_text || editing ? (
                          editing ? (
                            <textarea
                              className="page-text-editor"
                              value={page.ocr_text}
                              onChange={(e) => handlePageTextChange(idx, e.target.value)}
                              placeholder="Enter extracted text here..."
                            />
                          ) : (
                            <pre>{page.ocr_text}</pre>
                          )
                        ) : (
                          <p className="no-text">No text extracted from this page</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : null}

        <div className="modal-footer">
          {editing ? (
            <>
              <button
                className="modal-button cancel-button"
                onClick={handleCancelEdit}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                className="modal-button save-button"
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </>
          ) : (
            <button className="modal-button" onClick={onClose}>
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
