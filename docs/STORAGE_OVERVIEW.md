# Storage Overview

This document describes the dual-storage architecture used in the Genealogy AI project, including how documents are ingested, processed, and stored.

## Architecture Overview

The system uses **two complementary storage systems** working together:

1. **SQLite Database** - Stores structured genealogical data (source of truth)
2. **ChromaDB Vector Store** - Stores embeddings of document chunks for semantic search

```text
Document Upload
    ↓
┌──────────────────────────────────────────────────┐
│  Step 1: OCR Processing                          │
│  - Extract text from PDFs/images                 │
│  - Save OCR results to JSON files                │
└────────────────┬─────────────────────────────────┘
                 ↓
┌──────────────────────────────────────────────────┐
│  Step 2: Store Raw Documents (SQLite)            │
│  - One record per page                           │
│  - documents table with OCR text                 │
└────────────────┬─────────────────────────────────┘
                 ↓
┌──────────────────────────────────────────────────┐
│  Step 3: Entity Extraction (AI/LLM)              │
│  - Extract people, events, relationships         │
│  - Store structured data in SQLite               │
└────────────────┬─────────────────────────────────┘
                 ↓
┌──────────────────────────────────────────────────┐
│  Step 4: Reconciliation                          │
│  - Find duplicate people using fuzzy matching    │
│  - Merge duplicates (auto for 100% matches)      │
└────────────────┬─────────────────────────────────┘
                 ↓
┌──────────────────────────────────────────────────┐
│  Step 5: Vector Embeddings (ChromaDB)            │
│  - Chunk documents (1000 chars, 200 overlap)     │
│  - Generate embeddings using HuggingFace model   │
│  - Store in ChromaDB for semantic search         │
└──────────────────────────────────────────────────┘
```

## Storage System 1: SQLite Database

**Location:** `./genealogy.db` (default)

**Purpose:** Structured genealogical data - the **source of truth** for extracted entities and relationships.

### Schema

#### `documents` Table

Stores source documents and their OCR text.

- `id` - Primary key
- `source` - Original file path (unique)
- `page` - Page number
- `ocr_text` - Full text extracted via OCR
- `created_at` - Timestamp

#### `people` Table

Individual persons extracted from documents.

- `id` - Primary key
- `primary_name` - Main name for the person
- `notes` - Additional notes
- `confidence` - Confidence score (0-1) from extraction
- `source_document_id` - Foreign key to documents table
- `created_at` - Timestamp

#### `names` Table

Alternate names for people (spelling variants, maiden names, nicknames).

- `id` - Primary key
- `person_id` - Foreign key to people table
- `name` - Alternate name
- `name_type` - Type (birth, married, nickname, variant, etc.)
- `confidence` - Confidence score

#### `events` Table

Life events (births, deaths, marriages, occupations, etc.).

- `id` - Primary key
- `person_id` - Foreign key to people table
- `event_type` - Type of event (birth, death, marriage, etc.)
- `date` - Date (stored as string to handle uncertain/partial dates)
- `place` - Location
- `description` - Event details
- `confidence` - Confidence score
- `source_document_id` - Foreign key to documents table

#### `relationships` Table

Relationships between people.

- `id` - Primary key
- `source_person_id` - Foreign key to people table
- `target_person_id` - Foreign key to people table
- `relationship_type` - Type (parent, child, spouse, sibling, etc.)
- `confidence` - Confidence score
- `notes` - Additional notes
- `source_document_id` - Foreign key to documents table

### Key Operations

#### Ingestion

```python
db = GenealogyDatabase(db_path=Path("./genealogy.db"))
doc = db.add_document(source="file.pdf", page=1, ocr_text="...")
```

#### Entity Storage

```python
# After AI extraction
counts = db.store_extraction(extraction_result, document_id)
# Returns: {"people": 3, "events": 5, "relationships": 2}
```

#### Search

```python
people = db.get_person_by_name("John O'Byrne")
```

#### Merging Duplicates

```python
# Moves all events, relationships, and names from merge_id to keep_id
db.merge_people(keep_id=1, merge_id=2)
```

## Storage System 2: ChromaDB Vector Store

**Location:** `./chroma_db/` (default)

**Purpose:** Semantic search over document text using vector embeddings.

### Configuration

- **Embedding Model:** `all-MiniLM-L6-v2` (HuggingFace)
- **Collection Name:** `genealogy_documents`
- **Chunk Size:** 1000 characters
- **Chunk Overlap:** 200 characters
- **Separators:** Paragraphs (`\n\n`), lines (`\n`), sentences (`.`), clauses (`,`), words (` `)

### Document Chunking

Documents are split into overlapping chunks to:

1. Fit within embedding model limits
2. Maintain context across boundaries
3. Improve retrieval quality

Each chunk includes metadata:

```python
{
    "source": "file.pdf",
    "page": 1,
    "chunk_index": 0,
    "confidence": 0.98,
    "total_chunks": 5
}
```

### Chunk IDs

Generated from source, page, and chunk index:

```text
filename_p1_c0
filename_p1_c1
filename_p2_c0
...
```

### Key Operations

#### Adding Chunks

```python
chroma_store = ChromaStore(persist_directory=Path("./chroma_db"))
chunks = chunker.chunk_ocr_results(ocr_results)
chroma_store.add_chunks(chunks)
```

#### Semantic Search

```python
# Returns list of (text, metadata, score) tuples
results = chroma_store.search(
    query="John O'Byrne steamboat accident",
    k=5
)
```

#### Search by Source

```python
# Search within a specific document
results = chroma_store.search_by_source(
    source_path=Path("file.pdf"),
    query="marriage date",
    k=5
)
```

## Data Flow: Complete Pipeline

### 1. Document Upload (Web API)

**Endpoint:** `POST /api/upload`

**Flow:**

1. File uploaded via multipart/form-data
2. Saved to `./originals/` directory
3. Full pipeline triggered automatically

### 2. OCR Processing

**Module:** `src/backend/genealogy_ai/ingestion/ocr.py`

**Output Location:** `./ocr_output/` (JSON files)

**Process:**

- PDF → Extract images → OCR each page
- Images → OCR directly
- Text files → Read directly (no OCR needed)

**OCR Result:**

```python
OCRResult(
    text="...",
    source_path=Path("file.pdf"),
    page_number=1,
    confidence=0.98,
    metadata={"format": "pdf", "dpi": 300}
)
```

### 3. SQLite Storage

**Module:** `src/backend/genealogy_ai/storage/sqlite.py`

One `Document` record per page:

```python
doc = db.add_document(
    source="file.pdf",
    page=1,
    ocr_text="Full page text..."
)
```

### 4. Entity Extraction

**Module:** `src/backend/genealogy_ai/agents/extract_entities.py`

**Process:**

1. Load extraction prompt from `prompts/extraction.md`
2. Send OCR text + context to LLM (OpenAI by default)
3. LLM returns structured JSON with:
   - `people` - List of PersonData objects
   - `events` - List of EventData objects
   - `relationships` - List of RelationshipData objects

**Storage:**

```python
extractor = EntityExtractor()
result = extractor.extract(text=doc.ocr_text, source=doc.source, page=doc.page)
counts = db.store_extraction(result, doc.id)
```

**Three-Pass Storage:**

1. **Pass 1:** Create all `people` records, build name-to-ID mapping
2. **Pass 2:** Create all `events`, linking to people by name
3. **Pass 3:** Create all `relationships`, linking people by name

### 5. Reconciliation

**Module:** `src/backend/genealogy_ai/agents/reconcile_people.py`

**Process:**

1. Compare all person pairs using:
   - **Name normalization** (handles "Last, First" vs "First Last", punctuation)
   - **Fuzzy matching** (RapidFuzz library, default threshold: 85%)
   - **Birth date comparison** (exact match = high confidence)
   - **Birth place comparison** (fuzzy match, weighted less than name)
   - **Death date comparison** (exact match = additional signal)

2. Calculate overall confidence from individual signals

3. Return sorted list of `DuplicateCandidate` objects

**Auto-Merge:**

- Upload API: Auto-merges 100% confidence matches
- CLI: Configurable threshold with `--auto-approve --auto-threshold 0.95`

**Merge Operation:**

```python
db.merge_people(keep_id=1, merge_id=2)

```

- Transfers all alternate names to kept person
- Updates all events to point to kept person
- Updates all relationships to point to kept person
- Deletes merged person record

### 6. Vector Embeddings

**Module:** `src/backend/genealogy_ai/ingestion/chunking.py` + `storage/chroma.py`

**Process:**

1. **Chunk:** Split OCR text into ~1000 char chunks with 200 char overlap
2. **Embed:** Generate vectors using `all-MiniLM-L6-v2` (384 dimensions)
3. **Store:** Add to ChromaDB with metadata

**ChromaDB Structure:**

- Persistent storage in `./chroma_db/`
- SQLite backend (chroma.sqlite3)
- Multiple collection directories (one per collection)
- Automatic indexing for similarity search

## CLI Commands

### Ingest Only

```bash
geneai ingest file.pdf --db ./genealogy.db --chroma-dir ./chroma_db

```

**Does:** OCR → SQLite documents → Chunking → ChromaDB

**Does NOT:** Extract entities (requires API key)

### Extract Entities

```bash
geneai extract --db ./genealogy.db

```

**Requires:** OPENAI_API_KEY in .env

**Does:** Reads documents from SQLite → LLM extraction → Stores structured data

### Reconcile Duplicates

```bash
# Interactive mode (prompt for each match)
geneai reconcile --db ./genealogy.db

# Auto-approve exact matches only
geneai reconcile --auto-approve --auto-threshold 1.0

# Auto-approve 95%+ matches
geneai reconcile --auto-approve --auto-threshold 0.95
```

### Search Vector DB

```bash
geneai search "John O'Byrne steamboat" --limit 5
```

### View Statistics

```bash
geneai stats --db ./genealogy.db --chroma-dir ./chroma_db
```

## File Locations

| Purpose | Default Path | Configurable |
| ------- | ------------ | ------------ |
| Original files | `./originals/` | Yes (via config) |
| OCR output | `./ocr_output/` | Yes (via CLI/config) |
| SQLite database | `./genealogy.db` | Yes (via CLI/config) |
| ChromaDB vector store | `./chroma_db/` | Yes (via CLI/config) |

## Web API Endpoints

### Upload & Process

`POST /api/upload`

- Runs full pipeline (OCR → Extract → Reconcile → Embed)

### Documents

- `GET /api/documents` - List all documents
- `GET /api/documents/{id}` - Get document details
- `DELETE /api/documents/{id}` - Delete document and cascade delete entities
- `GET /api/documents/{id}/chunks` - Get vector chunks for document
- `POST /api/documents/{id}/extract` - Re-run entity extraction

### Chat

- `POST /api/chat` - Query using RAG (Retrieval-Augmented Generation)
  - Searches ChromaDB for relevant chunks
  - Queries SQLite for structured data
  - Sends context to LLM for answer

### Management

- `POST /api/ingest` - Ingest files without extraction
- `GET /api/stats` - Get database statistics

### Family Tree

- `GET /api/tree/people` - List all people
- `GET /api/tree/people/{id}` - Get person details with events and relationships
- `GET /api/tree/duplicates` - Find potential duplicate people

## Design Rationale

### Why Two Storage Systems?

#### SQLite (Structured Data)

**Strengths:**

- ✅ Precise queries (find all events for person X)
- ✅ Relationships and foreign keys
- ✅ Transactions and data integrity
- ✅ Source of truth for facts
- ✅ GEDCOM export compatibility

**Use Cases:**

- Finding specific people by name
- Listing all events for a person
- Building family trees
- Generating reports
- Data export (GEDCOM)

#### ChromaDB (Vector Store)

**Strengths:**

- ✅ Semantic search ("ship accidents in 1871")
- ✅ Finds relevant context even with different wording
- ✅ Works with partial/fuzzy information
- ✅ Retrieval-Augmented Generation (RAG) for chat

**Use Cases:**

- "Tell me about John's work history"
- "What happened on Martha's Vineyard?"
- Exploratory research questions
- Finding relevant document passages
- Supporting LLM context retrieval

### Why Not Just One?

A **single SQLite database** would require:

- Manual indexing strategies for semantic search
- No embedding model integration
- Difficult fuzzy/semantic queries

A **vector store only** would lack:

- Structured relationships between entities
- Precise data queries
- Referential integrity
- Easy export to GEDCOM

The **dual system** provides:

- **Precision** when you know what you're looking for (SQLite)
- **Discovery** when you're exploring (ChromaDB)
- **Best of both worlds** for genealogical research

## Backup & Recovery

### SQLite Backup

```bash
# Simple file copy
cp genealogy.db genealogy.db.backup

# Or use SQLite backup command
sqlite3 genealogy.db ".backup genealogy.db.backup"
```

### ChromaDB Backup

```bash
# Copy entire directory
cp -r chroma_db/ chroma_db.backup/
```

### Complete Restore

```bash
# Restore SQLite
cp genealogy.db.backup genealogy.db

# Restore ChromaDB
rm -rf chroma_db/
cp -r chroma_db.backup/ chroma_db/
```

## Performance Considerations

### SQLite

- **Indexes:** Automatically created on primary keys and foreign keys
- **Full-text search:** Can be added with FTS5 for name searching
- **Query optimization:** Use `.explain query plan` in sqlite3 CLI

### ChromaDB

- **Embedding cache:** Reuses embeddings for identical text
- **Batch operations:** Add chunks in batches for better performance
- **Memory usage:** HuggingFace model runs on CPU by default
- **Disk space:** ~1-2% of text size (for embeddings + metadata)

### Chunking Strategy

- **1000 chars** balances context vs granularity
- **200 char overlap** prevents context loss at boundaries
- **Logical separators** preserve sentence/paragraph structure

## Troubleshooting

### Issue: Duplicate people not merging

**Cause:** Confidence threshold too high
**Solution:** Lower `min_confidence` or `auto_threshold` in reconcile command

### Issue: Poor semantic search results

**Cause:** Chunks too large/small, or wrong embedding model
**Solution:** Adjust `chunk_size` in ingestion, or try different embedding model

### Issue: Extraction missing entities

**Cause:** OCR quality, LLM prompt, or model limitations
**Solution:**

- Improve OCR (higher DPI)
- Refine extraction prompt in `prompts/extraction.md`
- Try different LLM model

### Issue: Vector DB taking too much space

**Cause:** Too many chunks or large metadata
**Solution:** Increase chunk size, remove unnecessary metadata fields

## Future Enhancements

### Planned

- [ ] GEDCOM import/export integration with vector search
- [ ] Historical event timeline visualization
- [ ] Source citation tracking in vector chunks
- [ ] Multi-language OCR and extraction support
- [ ] Graph database integration for complex relationship queries

### Under Consideration

- [ ] PostgreSQL option for larger datasets
- [ ] Alternative embedding models (OpenAI, Cohere)
- [ ] Incremental vector updates (update chunks when documents edited)
- [ ] Vector search filtering by date ranges
- [ ] Hybrid search combining SQL + vector results

## Summary

The Genealogy AI storage system uses a **dual-storage architecture**:

1. **SQLite** - Structured source of truth (people, events, relationships)
2. **ChromaDB** - Semantic search over document text

Together, they enable:

- ✅ Precise genealogical queries
- ✅ Semantic document search
- ✅ AI-powered entity extraction
- ✅ Duplicate detection and merging
- ✅ RAG-powered conversational interface

This architecture balances the need for **structured genealogical data** with the power of **semantic AI search**, providing researchers with both precision and discovery capabilities.
