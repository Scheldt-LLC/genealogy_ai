# Quick Start Guide - Document Ingestion

This guide will help you get started with ingesting genealogical documents using the Genealogy AI ingestion module.

## Prerequisites

### System Dependencies

**Tesseract OCR** is required for text extraction from images and PDFs.

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

### Python Dependencies

Install the project in development mode:

```bash
# Install all dependencies
pip install -e .

# Or with development tools
pip install -e ".[dev]"

# Optional: Install PaddleOCR for better handwriting support
pip install -e ".[paddleocr]"
```

## Basic Usage

### 1. Ingest Documents

The `ingest` command processes PDF or image files, extracts text using OCR, and stores the results in both SQLite and Chroma vector databases.

```bash
# Ingest a single PDF
geneai ingest scans/family_record.pdf

# Ingest multiple files
geneai ingest scans/*.pdf

# Ingest with custom settings
geneai ingest scans/*.pdf \
  --output-dir ./my_ocr_output \
  --db ./my_genealogy.db \
  --chroma-dir ./my_vector_db \
  --chunk-size 1500 \
  --save-images
```

#### Command Options

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

```
your-project/
├── ocr_output/              # Raw OCR outputs
│   ├── document1_ocr.json   # OCR results in JSON
│   ├── document2_ocr.json
│   └── ...
├── genealogy.db             # SQLite database (structured facts)
└── chroma_db/               # Vector database (semantic search)
    └── ...
```

## What Gets Stored Where

### OCR Output Directory (`ocr_output/`)

- Raw OCR JSON files with full text and metadata
- Preserved forever for traceability
- Optional: extracted page images

### SQLite Database (`genealogy.db`)

- Documents table: source documents and pages
- People, events, relationships (added later by extraction agents)
- This is the **source of truth** for genealogical facts

### Chroma Vector Database (`chroma_db/`)

- Text chunks with embeddings for semantic search
- Used to find similar content across documents
- **Not** the source of truth - used for discovery only

## Example Workflow

```bash
# 1. Install dependencies
brew install tesseract
pip install -e .

# 2. Create a directory for your scans
mkdir -p scans
# ... add your PDF/image files to scans/

# 3. Ingest documents
geneai ingest scans/*.pdf --save-images

# 4. Check what was ingested
geneai stats

# 5. Search for content
geneai search "birth"
geneai search "marriage certificate"
geneai search "John Byrne"
```

## Supported File Formats

- **PDF** (`.pdf`)
- **Images** (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`)

## Performance Tips

- **DPI Setting**: Higher DPI (e.g., 400-600) improves OCR accuracy but takes longer
- **Chunk Size**: Smaller chunks (500-1000) work better for dense documents
- **Save Images**: Only use `--save-images` if you need to review page images later

## Next Steps

After ingestion, the next steps are:

1. **Entity Extraction**: Extract people, dates, places, relationships from OCR text
2. **Reconciliation**: Identify and merge duplicate people/events
3. **Family Tree Queries**: Query the structured database for genealogical information

These features will be implemented in the next phase.

## Troubleshooting

### "tesseract not found"

Make sure Tesseract is installed and in your PATH:

```bash
which tesseract  # Should show the path to tesseract
tesseract --version  # Should show version info
```

### Low OCR Accuracy

- Increase DPI: `--dpi 400` or higher
- Ensure scans are high quality and well-lit
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
