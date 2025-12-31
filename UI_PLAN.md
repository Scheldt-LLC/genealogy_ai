# Genealogy AI - UI Plan

## Tech Stack

### Backend
- **Quart** - Async Python web framework (Flask-like but async)
- **FastAPI/Quart API** - RESTful endpoints for file upload, extraction, queries
- **WebSockets** - Real-time chat interface for Q&A
- **Existing CLI backend** - Reuse all the logic we built

### Frontend
- **Vite + React** - Modern build tooling and component framework
- **React Router** - Navigation
- **TanStack Query** - Data fetching and caching
- **D3.js / Vis.js / React Flow** - Family tree visualization
- **Tailwind CSS** - Styling

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                │
│  ┌────────────┬──────────────┬──────────────────────┐  │
│  │  Upload    │   Chat       │   Tree               │  │
│  │  Interface │   Interface  │   Visualization      │  │
│  └────────────┴──────────────┴──────────────────────┘  │
│                         ↕ HTTP/WebSocket               │
└─────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────┐
│                  Quart Backend (Python)                 │
│  ┌────────────┬──────────────┬──────────────────────┐  │
│  │  File      │   LLM        │   Graph              │  │
│  │  Upload    │   Query      │   Builder            │  │
│  │  API       │   Engine     │   API                │  │
│  └────────────┴──────────────┴──────────────────────┘  │
│                         ↕                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │    Existing Backend (CLI Functions)             │   │
│  │  • OCR Ingestion    • Entity Extraction        │   │
│  │  • SQLite Storage   • Reconciliation           │   │
│  │  • Vector Search    • Citations                │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Core Pages/Features

### 1. Upload & Ingest
**URL:** `/upload`

**Features:**
- Drag & drop file upload (PDF, images, TXT)
- Multi-file upload support
- Progress indicators for:
  - OCR processing
  - Entity extraction
  - Vector embedding
- View upload history
- Re-process documents if needed

**Backend API:**
```python
POST /api/upload          # Upload files
GET  /api/documents       # List all documents
GET  /api/documents/:id   # Get document details
POST /api/documents/:id/reprocess  # Re-extract entities
```

---

### 2. Chat Interface
**URL:** `/chat`

**Features:**
- Natural language Q&A about genealogy data
- Example prompts:
  - "Who were John O'Byrne's children?"
  - "When did Anna Caufman Byrne die?"
  - "Show me all people born in Ireland"
- Show source citations with links to original documents
- Conversation history
- Suggested follow-up questions

**Backend API:**
```python
WebSocket /api/chat       # Real-time chat
POST /api/query           # HTTP alternative for queries
GET  /api/chat/history    # Get conversation history
```

**Query Engine:**
- Use vector search to find relevant document chunks
- Feed context + question to LLM
- Extract structured data from SQLite for precise answers
- Always cite sources

---

### 3. Family Tree Visualization
**URL:** `/tree`

**Features:**
- Interactive graph visualization
- Click person → show details panel:
  - Birth/death dates and places
  - Events
  - Source citations
  - Relationships
- Expand/collapse branches
- Filter by:
  - Time period
  - Location
  - Confidence score
- Export view as image
- Click citation → view original document

**Backend API:**
```python
GET  /api/tree/:person_id   # Get tree data for person
GET  /api/graph/all         # Get entire family graph
GET  /api/people/:id        # Get person details
```

**Graph Data Structure:**
```json
{
  "nodes": [
    {
      "id": 1,
      "name": "John O'Byrne",
      "birth": "1826-09-12",
      "death": "1905-04-15",
      "confidence": 0.95
    }
  ],
  "edges": [
    {
      "source": 1,
      "target": 2,
      "type": "spouse",
      "confidence": 1.0
    }
  ]
}
```

---

### 4. Document Viewer (Modal/Sidebar)
**Features:**
- View original scanned documents
- Highlight OCR'd text
- Show extracted entities overlaid on document
- Zoom, pan, rotate
- Page navigation for multi-page PDFs

**Backend API:**
```python
GET  /api/documents/:id/file      # Get original file
GET  /api/documents/:id/ocr       # Get OCR JSON with positions
```

---

### 5. Review & Reconciliation (Future)
**URL:** `/review`

**Features:**
- List potential duplicates
- Side-by-side comparison
- Show source documents for both
- Approve/reject/edit merge
- Batch operations

**Backend API:**
```python
GET   /api/reconcile/candidates   # Get duplicate candidates
POST  /api/reconcile/merge        # Merge two people
POST  /api/reconcile/reject       # Mark as not duplicates
```

---

## Development Phases

### Phase 1 - Foundation (Week 1-2)
- [x] Backend CLI complete
- [ ] Set up Quart backend with basic API
- [ ] Set up Vite + React frontend
- [ ] File upload interface + API
- [ ] Document list view
- [ ] Basic navigation

### Phase 2 - Core Features (Week 3-4)
- [ ] Chat interface (WebSocket)
- [ ] LLM query engine with RAG
- [ ] Tree visualization (basic)
- [ ] Person detail views
- [ ] Source citation viewer

### Phase 3 - Polish (Week 5-6)
- [ ] Document viewer (PDF/image)
- [ ] Interactive tree (expand/collapse)
- [ ] Reconciliation UI
- [ ] Export features
- [ ] Error handling & loading states

### Phase 4 - Deployment
- [ ] Docker containerization
- [ ] Production build
- [ ] Documentation
- [ ] Demo with sample data

---

## API Design

### File Upload Flow
```
1. User uploads file(s) via /api/upload
2. Backend saves to originals/
3. Backend triggers OCR (async job)
4. Backend triggers extraction (async job)
5. Frontend polls /api/jobs/:id for status
6. On completion, redirect to document view
```

### Chat Query Flow
```
1. User types question
2. Frontend sends via WebSocket
3. Backend:
   - Searches vector DB for relevant chunks
   - Queries SQLite for structured data
   - Combines context + question → LLM
   - Streams response back
4. Frontend displays with typing animation
5. Show citations below answer
```

### Tree Rendering Flow
```
1. User clicks "View Tree" for person
2. Frontend calls /api/tree/:person_id
3. Backend:
   - Gets person + 2 generations (parents, children)
   - Builds graph structure
   - Returns JSON
4. Frontend renders with D3/Vis.js
5. User clicks node → fetch more via /api/people/:id
```

---

## File Structure

```
genealogy-ai/
├── backend/                    # Quart backend
│   ├── api/
│   │   ├── __init__.py
│   │   ├── upload.py          # File upload endpoints
│   │   ├── chat.py            # Chat/query endpoints
│   │   ├── tree.py            # Tree/graph endpoints
│   │   ├── documents.py       # Document CRUD
│   │   └── websocket.py       # WebSocket handlers
│   ├── services/
│   │   ├── query_engine.py    # LLM + RAG query logic
│   │   ├── graph_builder.py   # Build family tree graphs
│   │   └── jobs.py            # Background job processing
│   ├── app.py                 # Quart app initialization
│   └── config.py              # Backend config
│
├── frontend/                   # Vite + React
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Upload.tsx
│   │   │   ├── Chat.tsx
│   │   │   ├── Tree.tsx
│   │   │   └── Documents.tsx
│   │   ├── components/
│   │   │   ├── FileUpload.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── FamilyTree.tsx
│   │   │   ├── PersonCard.tsx
│   │   │   └── DocumentViewer.tsx
│   │   ├── hooks/
│   │   │   ├── useChat.ts
│   │   │   ├── useTree.ts
│   │   │   └── useUpload.ts
│   │   ├── services/
│   │   │   └── api.ts         # API client
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── genealogy_ai/              # Existing CLI backend (reused)
│   ├── ingestion/
│   ├── agents/
│   ├── storage/
│   └── ...
│
└── pyproject.toml
```

---

## Next Steps

1. **Set up Quart backend**
   - Create `backend/` directory
   - Basic Quart app with CORS
   - Test endpoint: `GET /api/health`

2. **Set up Vite frontend**
   - Create `frontend/` directory
   - Initialize Vite + React + TypeScript
   - Basic routing (Upload, Chat, Tree pages)

3. **First working feature: File Upload**
   - Build upload UI
   - Implement `/api/upload` endpoint
   - Trigger ingestion pipeline
   - Show progress/results

4. **Second feature: Chat Interface**
   - Build chat UI
   - Implement WebSocket chat
   - Connect to LLM query engine

5. **Third feature: Tree Visualization**
   - Build tree component with D3/Vis.js
   - Implement graph API
   - Interactive person details

---

## Technologies & Libraries

### Backend Dependencies (add to pyproject.toml)
```toml
quart = ">=0.19.0"
quart-cors = ">=0.7.0"
python-multipart = ">=0.0.6"  # File uploads
```

### Frontend Dependencies (package.json)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "@tanstack/react-query": "^5.0.0",
    "axios": "^1.6.0",
    "d3": "^7.8.0",
    "react-dropzone": "^14.2.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.3.0"
  }
}
```

---

## Open Questions

1. **Authentication?** (Phase 1: None, Phase 2: Simple password, Phase 3: OAuth)
2. **Multi-user?** (Phase 1: Single user, Phase 2: Consider multi-tenancy)
3. **Real-time collaboration?** (Future consideration)
4. **Mobile support?** (Responsive design, Phase 2)

---

## Success Criteria

**Phase 1 MVP:**
- ✅ Upload a document
- ✅ See it ingested and extracted
- ✅ Ask questions via chat
- ✅ View basic family tree
- ✅ Click person to see details
- ✅ See source citations

**Phase 2 Polish:**
- ✅ Interactive tree (zoom, pan, expand)
- ✅ Document viewer overlay
- ✅ Reconciliation workflow
- ✅ Export options
- ✅ Good error handling

**Phase 3 Production:**
- ✅ Docker deployment
- ✅ Performance optimized
- ✅ User documentation
- ✅ Demo video/site
