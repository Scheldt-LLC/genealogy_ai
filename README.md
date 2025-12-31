# Genealogy AI
Extract genealogical information from historical documents using OCR and LLMs.


[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Overview

Genealogy AI ingests scanned historical family documents (typed, handwritten, photocopied), extracts genealogical information using OCR and Large Language Models, and builds a structured, auditable family tree.

### Core Principles

- **Preserve Original Sources**: Original documents are never modified or deleted
- **Ground Truth Separation**: Clear distinction between source documents and AI interpretations
- **Human-in-the-Loop**: AI suggestions require human approval for critical operations
- **Local-First**: Works entirely offline; cloud integration is optional
- **Open Source**: Transparent algorithms, prompts, and schemas

## Features

- **Multi-Format Support**: Process PDFs, images (JPEG, PNG, TIFF, BMP), and plain text files
- **Recursive Ingestion**: Automatically process entire directory trees of documents
- **Handwriting Support**: Optional PaddleOCR for handwritten documents
- **Entity Extraction**: Automatically extract people, dates, places, and relationships
- **Smart Reconciliation**: Detect possible duplicates with confidence scoring
- **Auditable**: Every fact links back to its source document
- **Export**: Generate GEDCOM files for compatibility with other genealogy software
- **Vector Search**: Semantic search across all documents using embeddings

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Tesseract OCR (see [installation instructions](#installing-tesseract))

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Scheldt-LLC/genealogy-ai.git
cd genealogy-ai
```

2. Install with uv:
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

3. Set up your configuration:
```bash
cp examples/config.example.yaml config.yaml
# Edit config.yaml with your settings
```

### Installing Tesseract

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download installer from [GitHub releases](https://github.com/UB-Mannheim/tesseract/wiki)

## Usage

### Web Application

**Development Mode** (with hot reload):

```bash
# Terminal 1: Start the backend (Quart server on port 5001)
cd src/backend
uv run python app.py

# Terminal 2: Start the frontend (Vite dev server on port 5173)
cd src/frontend
npm run dev
```

Then open your browser to `http://localhost:5173`

**Production Mode** (single server):

```bash
# Build the frontend
cd src/frontend
npm run build

# Start the backend (serves frontend + API on port 5001)
cd ../backend
uv run python app.py
```

Then open your browser to `http://localhost:5001`

### CLI Workflow

1. **Ingest Documents**

Place your original documents in the `originals/` directory (organized in subdirectories if desired), then run:

```bash
# Recursively ingest all supported files in originals/ directory
geneai ingest originals/ --recursive

# Or ingest specific files/patterns
geneai ingest originals/*.pdf originals/*.jpg
```

Supported file types: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.txt`

2. **Extract Entities**
```bash
geneai extract
```

3. **Reconcile Duplicates**
```bash
# Interactive reconciliation
geneai reconcile

# Auto-approve exact matches (100%)
geneai reconcile --auto-approve --auto-threshold 1.0

# Auto-approve matches above 95%
geneai reconcile --auto-approve --auto-threshold 0.95
```

4. **Query Family Tree**
```bash
geneai tree --person "John Byrne"
```

5. **Export Data**
```bash
geneai export family_tree.ged
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `geneai ingest <files> --recursive` | Import scanned documents (recursively process directories) |
| `geneai extract` | Extract entities from ingested documents using AI |
| `geneai reconcile [--auto-approve] [--auto-threshold 0.95]` | Find and merge duplicate people with human approval |
| `geneai tree --person <name>` | Display family tree for a person |
| `geneai search <query>` | Semantic search across documents |
| `geneai export <output.ged>` | Export data to GEDCOM format |
| `geneai stats` | Show database statistics |
| `geneai version` | Display version information |

## Architecture

```
Scanned Documents (PDF/Images)
        ↓
    OCR Layer (Tesseract/PaddleOCR)
        ↓
   Raw Text + Layout
        ↓
Entity Extraction Agent (LangChain + LLM)
        ↓
Structured Data (SQLite)
        ↓
Reconciliation Agent
        ↓
    Family Tree

Parallel: Text → Embeddings → Vector DB (ChromaDB)
```

### Data Storage

1. **Ground Truth (Immutable)**
   - Original documents stored on disk
   - OCR JSON output preserved

2. **Structured Database (SQLite)**
   - People, events, relationships
   - Confidence scores
   - Source citations

3. **Vector Database (ChromaDB)**
   - Document chunks
   - Semantic search
   - Never stores canonical facts

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.

## Configuration

Create a `config.yaml` file:

```yaml
# LLM Provider (choose one)
llm:
  provider: "openai"  # or "anthropic", "ollama"
  model: "gpt-4-turbo-preview"
  api_key: "${OPENAI_API_KEY}"  # or set in environment

# OCR Settings
ocr:
  engine: "tesseract"  # or "paddleocr"
  languages: ["eng"]
  dpi: 300

# Storage
storage:
  data_dir: "./data"
  db_path: "./data/genealogy.db"
  vector_db_path: "./data/chroma_db"

# Processing
processing:
  confidence_threshold: 0.7
  chunk_size: 1000
  chunk_overlap: 200
```

## Development

### Setup Development Environment

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Code Quality

This project uses modern Python tooling:

- **[ruff](https://github.com/astral-sh/ruff)**: Linting and formatting (replaces black, flake8, isort)
- **[mypy](https://mypy-lang.org/)**: Static type checking
- **[pytest](https://pytest.org/)**: Testing framework

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy genealogy_ai

# Run tests
pytest

# Run tests with coverage
pytest --cov=genealogy_ai --cov-report=html
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit

# Integration tests
pytest tests/integration

# Specific test file
pytest tests/unit/test_ocr.py

# With coverage
pytest --cov=genealogy_ai
```

## Project Structure

```
genealogy-ai/
├── src/
│   ├── backend/
│   │   ├── genealogy_ai/      # Main package
│   │   │   ├── ingestion/     # OCR and document processing
│   │   │   ├── agents/        # LLM agents (extraction, reconciliation)
│   │   │   ├── storage/       # Database interfaces
│   │   │   ├── schemas/       # Data models and validation
│   │   │   ├── prompts/       # LLM prompt templates
│   │   │   └── cli/           # Command-line interface
│   │   ├── app.py            # Quart web application
│   │   └── config.py         # Backend configuration
│   └── frontend/             # React + TypeScript + Vite
│       ├── src/
│       ├── public/
│       └── package.json
├── tests/                    # Test suite
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── docs/                     # Documentation
├── examples/                 # Example configurations and scripts
└── data/                     # Generated data (not in git)
```

## Roadmap

### Phase 1: MVP ✅ Complete
- [x] Project setup
- [x] OCR ingestion (Tesseract, multi-format support)
- [x] Entity extraction (LLM-powered with confidence scoring)
- [x] SQLite storage (with citation tracking)
- [x] ChromaDB vector storage
- [x] Reconciliation agent (fuzzy matching with human approval)
- [x] Complete CLI (ingest, extract, reconcile, tree, export, search, stats)

### Phase 2: Accuracy & UI 🚧 In Progress
- [x] Confidence thresholds (auto-approve with configurable threshold)
- [x] Web interface foundation (Quart backend + Vite/React frontend)
- [ ] File upload interface
- [ ] Chat interface for Q&A
- [ ] Tree visualization
- [ ] Manual review tools
- [ ] Improved reconciliation

### Phase 3: Cloud (Optional)
- [ ] Azure AI Vision adapter
- [ ] Azure AI Search adapter
- [ ] Cloud deployment guide

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Key Contribution Areas

- OCR accuracy improvements
- LLM prompt engineering
- Reconciliation algorithms
- Documentation
- Test coverage
- Bug fixes

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [LangChain](https://www.langchain.com/)
- OCR powered by [Tesseract](https://github.com/tesseract-ocr/tesseract)
- Vector DB by [ChromaDB](https://www.trychroma.com/)

## Support

- **Issues**: [GitHub Issues](https://github.com/Scheldt-LLC/genealogy-ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Scheldt-LLC/genealogy-ai/discussions)
- **Documentation**: [docs/](docs/)

---

Made with care for preserving family history.
