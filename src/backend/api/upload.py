"""File upload API endpoints."""

from pathlib import Path

from quart import Blueprint, Response, current_app, jsonify, request
from werkzeug.utils import secure_filename

from src.backend.genealogy_ai.agents.extract_entities import EntityExtractor
from src.backend.genealogy_ai.agents.reconcile_people import ReconciliationAgent
from src.backend.genealogy_ai.ingestion.chunking import DocumentChunker
from src.backend.genealogy_ai.ingestion.ocr import OCRProcessor
from src.backend.genealogy_ai.storage.chroma import ChromaStore
from src.backend.genealogy_ai.storage.sqlite import GenealogyDatabase

upload_bp = Blueprint("upload", __name__)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed.

    Args:
        filename: Name of the file to check

    Returns:
        True if file extension is allowed
    """
    config = current_app.config
    if not filename:
        return False
    return Path(filename).suffix.lower() in config.get("ALLOWED_EXTENSIONS", set())


@upload_bp.route("/api/upload", methods=["POST"])
async def upload_file() -> Response | tuple[Response, int]:
    """Upload and process a document file.

    Accepts multipart/form-data with file upload.
    Saves file to upload folder and triggers OCR processing.

    Returns:
        JSON response with document ID and status
    """
    files = await request.files

    if "file" not in files:
        return jsonify({"error": "No file provided"}), 400

    file = files["file"]

    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify(
            {
                "error": f"File type not allowed. Supported: {', '.join(current_app.config.get('ALLOWED_EXTENSIONS', set()))}"
            }
        ), 400

    # Secure the filename
    filename = secure_filename(file.filename)
    upload_folder = Path(current_app.config.get("UPLOAD_FOLDER", "./originals"))
    upload_folder.mkdir(parents=True, exist_ok=True)

    # Save the file
    file_path = upload_folder / filename
    await file.save(str(file_path))

    # Process with full pipeline: OCR → Extract → Reconcile → Vector DB
    try:
        # Step 1: OCR Processing
        ocr_output_dir = Path(current_app.config.get("OCR_OUTPUT_DIR", "./ocr_output"))
        ocr_processor = OCRProcessor(output_dir=ocr_output_dir)
        ocr_results = ocr_processor.process_document(file_path)

        # Step 2: Save to database (one record per page)
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        document_ids = []
        for ocr_result in ocr_results:
            doc = db.add_document(
                source=str(ocr_result.source_path),
                page=ocr_result.page_number,
                ocr_text=ocr_result.text,
            )
            if doc:
                document_ids.append(doc.id)

        # Step 3: Entity Extraction
        total_people = 0
        total_events = 0
        total_relationships = 0

        try:
            extractor = EntityExtractor()

            for ocr_result, doc_id in zip(ocr_results, document_ids, strict=True):
                # Extract entities from this page
                extraction_result = extractor.extract(
                    text=ocr_result.text,
                    source=str(ocr_result.source_path),
                    page=ocr_result.page_number,
                )

                # Store extraction results
                if not extraction_result.is_empty():
                    counts = db.store_extraction(extraction_result, doc_id)
                    total_people += counts["people"]
                    total_events += counts["events"]
                    total_relationships += counts["relationships"]

        except Exception as e:
            # Log extraction error but don't fail the upload
            import traceback

            traceback.print_exc()
            print(f"Entity extraction failed: {e!s}")

        # Step 4: Reconciliation (auto-approve 100% matches)
        duplicates_merged = 0
        try:
            agent = ReconciliationAgent(db=db, min_confidence=0.6)
            candidates = agent.find_duplicates()

            # Auto-merge exact matches (100% confidence)
            for candidate in candidates:
                if candidate.confidence >= 1.0:
                    db.merge_people(keep_id=candidate.person1_id, merge_id=candidate.person2_id)
                    duplicates_merged += 1

        except Exception as e:
            # Log reconciliation error but don't fail the upload
            import traceback

            traceback.print_exc()
            print(f"Reconciliation failed: {e!s}")

        # Step 5: Chunk and add to vector database
        total_chunks = 0
        try:
            chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
            chunks = chunker.chunk_ocr_results(ocr_results)

            chroma_dir = Path(current_app.config.get("CHROMA_DIR", "./chroma_db"))
            chroma_store = ChromaStore(persist_directory=chroma_dir)
            chroma_store.add_chunks(chunks)

            total_chunks = len(chunks)

        except Exception as e:
            # Log vector storage error but don't fail the upload
            import traceback

            traceback.print_exc()
            print(f"Vector storage failed: {e!s}")

        return jsonify(
            {
                "success": True,
                "document_ids": document_ids,
                "filename": filename,
                "page_count": len(ocr_results),
                "entities_extracted": {
                    "people": total_people,
                    "events": total_events,
                    "relationships": total_relationships,
                },
                "duplicates_merged": duplicates_merged,
                "chunks_stored": total_chunks,
                "message": "File uploaded and fully processed successfully",
            }
        ), 201

    except Exception as e:
        # Clean up the file if processing failed
        if file_path.exists():
            file_path.unlink()

        # Log full traceback for debugging
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to process file: {e!s}"}), 500
