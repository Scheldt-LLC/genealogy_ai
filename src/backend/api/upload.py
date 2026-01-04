"""File upload API endpoints."""

from pathlib import Path

from quart import Blueprint, Response, current_app, jsonify, request
from werkzeug.utils import secure_filename

from src.backend.genealogy_ai.agents.build_entities import EntityBuilder, generate_batch_id
from src.backend.genealogy_ai.agents.extract_entities import EntityExtractor
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

    Form parameters:
        - file: Document file to upload (required)
        - engine: OCR engine ("tesseract" or "azure", default: "tesseract")
        - azure_key: Azure Document Intelligence key (optional)
        - azure_endpoint: Azure Document Intelligence endpoint (optional)
        - openai_key: OpenAI API key (optional)
        - document_type: Document type (e.g., "census", "portrait", optional)
        - family_name: Family name to assign to extracted people (optional)
        - family_side: Family side - "maternal" or "paternal" (optional)

    Returns:
        JSON response with document ID and status
    """
    files = await request.files
    form = await request.form

    if "file" not in files:
        return jsonify({"error": "No file provided"}), 400

    file = files["file"]
    engine = form.get("engine", "tesseract")
    azure_key = form.get("azure_key") or current_app.config.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    azure_endpoint = form.get("azure_endpoint") or current_app.config.get(
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
    )
    openai_key = form.get("openai_key") or current_app.config.get("OPENAI_API_KEY")
    document_type = form.get("document_type")
    family_name = form.get("family_name")
    family_side = form.get("family_side")

    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify(
            {
                "error": f"File type not allowed. Supported: {', '.join(current_app.config.get('ALLOWED_EXTENSIONS', set()))}"
            }
        ), 400

    # Secure the filename and make it unique to avoid conflicts
    import time

    original_filename = secure_filename(file.filename)
    filename_parts = original_filename.rsplit(".", 1)
    timestamp = str(int(time.time() * 1000))  # Millisecond timestamp

    if len(filename_parts) == 2:
        # Has extension
        unique_filename = f"{filename_parts[0]}_{timestamp}.{filename_parts[1]}"
    else:
        # No extension
        unique_filename = f"{original_filename}_{timestamp}"

    upload_folder = Path(current_app.config.get("UPLOAD_FOLDER", "./originals"))
    upload_folder.mkdir(parents=True, exist_ok=True)

    # Save the file with unique name
    file_path = upload_folder / unique_filename
    await file.save(str(file_path))

    # Process with full pipeline: OCR → Extract → Reconcile → Vector DB
    try:
        # Step 1: OCR Processing
        ocr_output_dir = Path(current_app.config.get("OCR_OUTPUT_DIR", "./ocr_output"))
        ocr_processor = OCRProcessor(
            output_dir=ocr_output_dir,
            engine=engine,
            azure_key=azure_key,
            azure_endpoint=azure_endpoint,
        )
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

                # Set document type if provided
                if document_type and doc.id:
                    db.update_document_type(document_id=doc.id, document_type=document_type)

        # Step 3: Entity Extraction and Staging (NEW PIPELINE)
        total_staged = 0
        auto_approved = 0
        needs_review = 0
        review_ids: list[int] = []

        try:
            # Generate unique batch ID for this upload
            batch_id = generate_batch_id()

            # Initialize extractor and builder
            extractor = EntityExtractor(api_key=openai_key)
            builder = EntityBuilder(db=db, auto_approve_threshold=0.95)

            # Extract entities from all pages and stage them
            for ocr_result, doc_id in zip(ocr_results, document_ids, strict=True):
                # Extract entities from this page
                extraction_result = extractor.extract(
                    text=ocr_result.text,
                    source=str(ocr_result.source_path),
                    page=ocr_result.page_number,
                )

                # Stage extraction results (don't insert to DB yet)
                if not extraction_result.is_empty():
                    counts = builder.stage_extraction(
                        extraction_result,
                        batch_id=batch_id,
                        document_id=doc_id,
                        family_name=family_name,
                        family_side=family_side,
                    )
                    total_staged += counts["people"]

            # Step 4: Consolidate, match, and auto-approve high-confidence matches
            if total_staged > 0:
                processing_result = builder.process_batch(batch_id, auto_approve=True)
                auto_approved = processing_result["auto_approved"]
                needs_review = processing_result["needs_review"]
                review_ids = processing_result["review_ids"]  # type: ignore[assignment]

        except Exception as e:
            # Log extraction error but don't fail the upload
            import traceback

            traceback.print_exc()
            print(f"Entity extraction/staging failed: {e!s}")

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
                "filename": original_filename,
                "page_count": len(ocr_results),
                "document_type": document_type,
                "family_name": family_name,
                "family_side": family_side,
                "entities_staged": total_staged,
                "entities_auto_approved": auto_approved,
                "entities_needs_review": needs_review,
                "review_ids": review_ids,
                "chunks_stored": total_chunks,
                "message": (
                    "File uploaded and processed successfully. "
                    f"{auto_approved} entities auto-approved, "
                    f"{needs_review} need review."
                ),
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
