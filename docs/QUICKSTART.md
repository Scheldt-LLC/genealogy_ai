# Quick Start Guide

This guide walks you through getting Genealogy AI running on your machine, from installation to your first document ingestion.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Running the Web Application](#running-the-web-application)
4. [Using the CLI](#using-the-cli)
5. [Next Steps](#next-steps)

## Prerequisites

### Required Software

1. **Python 3.11 or higher**

   ```bash
   python3 --version  # Should show 3.11+
   ```

2. **uv Package Manager** (recommended) or pip

   ```bash
   # Install uv
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Tesseract OCR** - Required for text extraction from images and PDFs

   **macOS:**

   ```bash
   brew install tesseract
   ```

   **Ubuntu/Debian:**

   ```bash
   sudo apt-get update
   sudo apt-get install tesseract-ocr
   ```

   **Windows:**
   Download the installer from [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

   Verify installation:

   ```bash
   tesseract --version
   ```

4. **Node.js 18+** (for web UI only)

   ```bash
   node --version  # Should show 18+
   ```

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Scheldt-LLC/genealogy-ai.git
   cd genealogy-ai
   ```

2. **Install Python dependencies:**

   ```bash
   # Create virtual environment and install
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e ".[dev]"
   ```

3. **(Optional) Install frontend dependencies:**

   ```bash
   cd src/frontend
   npm install
   cd ../..
   ```

## Running the Web Application

The web UI provides an intuitive interface for uploading documents, viewing OCR results, and exploring your family tree.

### Development Mode (with hot reload)

**Terminal 1 - Backend:**

```bash
# From project root
uv run hypercorn src.backend.app:app --bind 0.0.0.0:5001 --reload
```

**Terminal 2 - Frontend:**

```bash
# From project root
cd src/frontend
npm run dev
```

Then open your browser to `http://localhost:5173`

### Production Mode (single server)

```bash
# Build the frontend (one-time)
cd src/frontend
npm install && npm run build
cd ../..

# Start the backend (serves built frontend + API)
uv Using the CLI

### 1. Ingest Documentbackend.app:app --bind 0.0.0.0:5001
```

Then open your browser to `http://localhost:5001`

## Using the CLI

2. Check Statistic
The `ingest` command processes PDF or image files, extracts text using OCR, and stores the results in both SQLite and Chroma vector databases.

```bash
# Ingest a single PDF
geneai ingest scans/family_record.pdf

# Ingest multiple files
geneai ingest scans/*.pdf

# Ingest with custom settings
geneai ingest scans/*.pdf \
  # 3. Search Your Documents
  --db ./my_genealogy.db \
  --chroma-dir ./my_vector_db \
  --chunk-size 1500 \
  --save-images
```

### Command Options

- `--output-dir, -o`: Directory for OCR output (default: `./ocr_output`)
- `--db`: Path to SQLite database (default: `./genealogy.db`)
- `--chroma-dir`: Directory for Chroma vector database (default: `./chroma_db`)
- `--chunk-size`: Maximum characters per chunk (default: 1000)
- `--chunk-overlap`: Character overlap between chunks (default: 200)
- `--save-images`: Save extracted page images from PDFs
- `--dpi`: DPI for PDF to image conversion (default: 300)

### 2. View Statistics

Check what's been ingested:

```bash
geneai stats
```

### 3. Search Documents

Search the vector database for similar text:

```bash
# Basic search
geneai search "John Byrne"

# Limit results
geneai search "birth certificate" --limit 10
```

## File Structure After Ingestion

After running ingestion, you'll see:

```text
your-project/
├── ocr_output/              # Raw OCR outputs
│   ├── document1_ocr.json   # OCR results in JSON
│   ├── document2_ocr.json
│   └── ...
├── genealogy.db             # SQLite database (structured facts)
└── chroma_db/               # Vector database (semantic search)
    └── ...
```Next Steps

After your first successful ingestion:

1. **Extract Entities** - Pull out people, dates, places from your documents
   ```bash
   geneai extract
   ```

2. **Reconcile Duplicates** - Merge duplicate people with confidence scoring

   ```bash
   geneai reconcile
   ```

3. **Query Family Tree** - Explore relationships

   ```bash
   geneai tree --person "John Byrne"
   ```

4. **Export to GEDCOM** - Share with other genealogy software

  # What Gets Stored Where

   geneai export family_tree.ged

   ```text

For more information, see:
- Main [README.md](../README.md) for full feature list and architecture
- [STORAGE_OVERVIEW.md](STORAGE_OVERVIEW.md) for how data is organized
- [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines

## Understanding the File Structu

## What Gets Stored Where

### OCR Output Directory (`ocr_output/`)

- Raw OCR JSON files with full text and metadata
- Preserved forever for traceability
- Optional: extracted page images

### SQLite Database (`genealogy.db`)

- Documents table: source documents and pages
- People, events, relationships (added later by extraction agents)
- TCommon Workflows

### Complete CLI Workflow truth** for genealogical facts

### Chroma Vector Database (`chroma_db/`)
# Supported File Format
- Text chunks with embeddings for semantic search
- Used to find similar content across documents
- **Not** the source of truth - used for discovery only

## Example Workflow
# Performance Tipsnts
geneai ingest scans/*.pdf --save-images

# 4. Check what was ingested
geneai stats

# 5. Search for content
geneai search "birth"
geneai search "marriage certificate"
geneai search "John Byrne"
```

## Troubleshooting

- **PDF** (`.pdf`)
- **Images** (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`)

## Performance Tips

- **DPI Setting**: Higher DPI (e.g., 400-600) improves OCR accuracy but takes longer
- **Chunk Size**: Smaller chunks (500-1000) work better for dense documents
**"tesseract not found"**nly use `--save-images` if you need to review page images later

## Next Steps

After ingestion, the next steps are:

1. **Entity Extraction**: Extract people, dates, places, relationships from OCR text
2. **Reconciliation**: Identify and merge duplicate people/events
**Low OCR Accuracy**Queries**: Query the structured database for genealogical information

These features will be implemented in the next phase.

## Troubleshooting

**Out of Memory**

- Consider PaddleOCR for handwritten documents

### Out of Memory

- Process files one at a time instead of using wildcards
- Reduce DPI if processing very large PDFs

## Configuration

You can create a `.env` file in your project root to set default paths:

```env
# .env
GENEALOGY_DB_PATH=./data/genealogy.db
CHROMA_DB_PATH=./data/chroma_db
OCR_OUTPUT_PATH=./data/ocr_output
DEFAULT_DPI=300
DEFAULT_CHUNK_SIZE=1000
```

(Configuration loading will be implemented in a future update)
