"""Document API endpoints."""

import json
from pathlib import Path

from quart import Blueprint, Response, current_app, jsonify, request, send_file

from src.backend.genealogy_ai.agents.build_entities import EntityBuilder, generate_batch_id
from src.backend.genealogy_ai.agents.extract_entities import EntityExtractor
from src.backend.genealogy_ai.ingestion.chunking import DocumentChunker, OCRResult
from src.backend.genealogy_ai.storage.chroma import ChromaStore
from src.backend.genealogy_ai.storage.sqlite import Document, GenealogyDatabase

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/api/documents", methods=["GET"])
async def list_documents() -> Response | tuple[Response, int]:
    """Get list of all uploaded documents.

    Returns:
        JSON response with list of documents
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))

        # Return empty list if database doesn't exist yet
        if not db_path.exists():
            return jsonify(
                {
                    "success": True,
                    "count": 0,
                    "documents": [],
                }
            )

        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        # Query all documents and group by source
        all_docs = session.query(Document).order_by(Document.created_at.desc()).all()

        # Group pages by source document
        docs_by_source = {}
        for doc in all_docs:
            if doc.source not in docs_by_source:
                # Extract filename from source path
                source_path = Path(str(doc.source))
                filename = source_path.name if source_path.name else str(source_path)

                docs_by_source[doc.source] = {
                    "source": doc.source,
                    "filename": filename,
                    "pages": [],
                    "created_at": doc.created_at,
                }
            docs_by_source[doc.source]["pages"].append(doc.id)

        # Convert to list format
        documents_list = []
        for pages_info in docs_by_source.values():
            documents_list.append(
                {
                    "id": pages_info["pages"][0],  # Use first page ID as document ID
                    "filename": pages_info["filename"] or "Unknown",
                    "file_path": pages_info["source"],
                    "page_count": len(pages_info["pages"]),
                    "created_at": pages_info["created_at"],
                }
            )

        return jsonify(
            {
                "success": True,
                "count": len(documents_list),
                "documents": documents_list,
            }
        )

    except Exception as e:
        # Log the error for debugging
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to fetch documents: {e!s}"}), 500


@documents_bp.route("/api/documents/<int:document_id>/file", methods=["GET"])
async def get_document_file(document_id: int) -> Response | tuple[Response, int]:
    """Get the original file for a document.

    Args:
        document_id: ID of the document

    Returns:
        The original file for download/viewing
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))

        if not db_path.exists():
            return jsonify({"error": "Database not found"}), 404

        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        # Get the document to find its source file path
        document = session.query(Document).filter(Document.id == document_id).first()

        if not document:
            return jsonify({"error": "Document not found"}), 404

        file_path = Path(str(document.source))

        # Security check: ensure file is within allowed directories
        upload_folder = Path(current_app.config.get("UPLOAD_FOLDER", "./uploads"))
        try:
            file_path.resolve().relative_to(upload_folder.resolve())
        except ValueError:
            # File is not in upload folder, reject
            return jsonify({"error": "File not found"}), 404

        if not file_path.exists():
            return jsonify({"error": "File not found on disk"}), 404

        # Determine mimetype
        mimetype = None
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            mimetype = "application/pdf"
        elif suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}:
            mimetype = f"image/{suffix[1:] if suffix != '.jpg' else 'jpeg'}"
        elif suffix == ".txt":
            mimetype = "text/plain"

        # Send the file
        return await send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,  # Display in browser if possible
            attachment_filename=file_path.name,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to retrieve file: {e!s}"}), 500


@documents_bp.route("/api/documents/<int:document_id>/details", methods=["GET"])
async def get_document_details(document_id: int) -> Response | tuple[Response, int]:
    """Get detailed information about a document including OCR text.

    Args:
        document_id: ID of the document

    Returns:
        JSON response with document details including OCR text from all pages
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))

        if not db_path.exists():
            return jsonify({"error": "Database not found"}), 404

        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        # Get all documents with the same source as the requested document
        first_doc = session.query(Document).filter(Document.id == document_id).first()

        if not first_doc:
            return jsonify({"error": "Document not found"}), 404

        # Get all pages for this document
        all_pages = (
            session.query(Document)
            .filter(Document.source == first_doc.source)
            .order_by(Document.page)
            .all()
        )

        # Build response with all pages
        pages_data = []
        for doc in all_pages:
            pages_data.append(
                {
                    "page": doc.page,
                    "ocr_text": doc.ocr_text or "",
                }
            )

        return jsonify(
            {
                "success": True,
                "document_id": document_id,
                "filename": Path(str(first_doc.source)).name,
                "source": first_doc.source,
                "page_count": len(all_pages),
                "created_at": first_doc.created_at,
                "pages": pages_data,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to retrieve document details: {e!s}"}), 500


@documents_bp.route("/api/documents/<int:document_id>/update-text", methods=["POST"])
async def update_document_text(document_id: int) -> Response | tuple[Response, int]:
    """Update the OCR text for a document and regenerate vector embeddings.

    Args:
        document_id: ID of the document to update

    Expects JSON body with:
        - pages: List of page objects with page number and ocr_text

    Returns:
        JSON response indicating success or failure
    """
    try:
        data = await request.get_json()

        if not data or "pages" not in data:
            return jsonify({"error": "No pages data provided"}), 400

        pages_data = data["pages"]

        if not isinstance(pages_data, list):
            return jsonify({"error": "Pages must be a list"}), 400

        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))

        if not db_path.exists():
            return jsonify({"error": "Database not found"}), 404

        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        # Get the first document to find the source
        first_doc = session.query(Document).filter(Document.id == document_id).first()

        if not first_doc:
            return jsonify({"error": "Document not found"}), 404

        source_path = str(first_doc.source)

        # Get all documents for this source
        all_docs = (
            session.query(Document)
            .filter(Document.source == source_path)
            .order_by(Document.page)
            .all()
        )

        # Create a mapping of page number to document
        doc_by_page = {doc.page: doc for doc in all_docs}

        # Update each page in the database
        updated_pages = []
        for page_data in pages_data:
            page_num = page_data.get("page")
            new_text = page_data.get("ocr_text", "")

            if page_num in doc_by_page:
                doc = doc_by_page[page_num]
                doc.ocr_text = new_text
                updated_pages.append(doc)

        # Commit changes to database
        session.commit()

        # Now update vector embeddings
        # Step 1: Delete old chunks for this document from ChromaDB
        chroma_dir = Path(current_app.config.get("CHROMA_DIR", "./chroma_db"))

        if chroma_dir.exists():
            chroma_store = ChromaStore(persist_directory=chroma_dir)

            # Delete old chunks for this source
            chroma_store.delete_by_source(Path(source_path))

            # Step 2: Re-chunk the updated text
            ocr_results = []
            for doc in updated_pages:
                ocr_results.append(
                    OCRResult(
                        source_path=Path(str(doc.source)),
                        page_number=doc.page,
                        text=doc.ocr_text or "",
                    )
                )

            # Step 3: Create new chunks
            chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
            chunks = chunker.chunk_ocr_results(ocr_results)

            # Step 4: Add new chunks to vector database
            chroma_store.add_chunks(chunks)

        return jsonify(
            {
                "success": True,
                "message": "Document text updated and vector embeddings regenerated",
                "pages_updated": len(updated_pages),
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to update document text: {e!s}"}), 500


@documents_bp.route("/api/documents/<int:document_id>/type", methods=["POST"])
async def set_document_type(document_id: int) -> Response | tuple[Response, int]:
    """Set or change the document type.

    Args:
        document_id: ID of the document

    Body:
        - document_type: Type of document (e.g., "census", "portrait", "birth_certificate")

    Returns:
        JSON with success status
    """
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        document_type = data.get("document_type")
        if not document_type:
            return jsonify({"error": "document_type is required"}), 400

        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        db.update_document_type(document_id=document_id, document_type=document_type)

        return jsonify(
            {
                "success": True,
                "message": f"Document {document_id} type set to '{document_type}'",
            }
        ), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to set document type: {e!s}"}), 500


@documents_bp.route("/api/documents/<int:document_id>/people", methods=["GET"])
async def get_document_people(document_id: int) -> Response | tuple[Response, int]:
    """Get all people linked to a document.

    Args:
        document_id: ID of the document

    Query parameters:
        - link_type: Optional filter by link type (e.g., "extracted_from", "portrait_of")

    Returns:
        JSON with list of linked people
    """
    try:
        link_type = request.args.get("link_type", type=str)

        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        people = db.get_document_people(document_id=document_id, link_type=link_type)

        people_data = [
            {
                "person_id": person["person_id"],
                "name": person["name"],
                "link_type": person["link_type"],
                "notes": person["notes"],
                "family_name": person["family_name"],
                "family_side": person["family_side"],
            }
            for person in people
        ]

        return jsonify(
            {
                "success": True,
                "document_id": document_id,
                "people": people_data,
                "count": len(people_data),
            }
        ), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to get document people: {e!s}"}), 500


@documents_bp.route("/api/documents/reprocess", methods=["POST"])
async def reprocess_documents() -> Response | tuple[Response, int]:
    """Reprocess existing documents with entity extraction (with SSE progress).

    This endpoint streams progress updates using Server-Sent Events.

    Request body (JSON):
        - document_ids: Optional list of specific document IDs to reprocess
        - openai_key: Optional OpenAI API key override
        - family_name: Optional family name to assign to extracted people
        - family_side: Optional family side (maternal/paternal)
        - auto_approve_threshold: Optional threshold for auto-approval (default 0.95)

    Returns:
        Server-Sent Events stream with progress updates
    """
    # Get request data outside the generator (where we have access to the request context)
    data = await request.get_json() or {}
    document_ids = data.get("document_ids")
    openai_key = data.get("openai_key") or current_app.config.get("OPENAI_API_KEY")
    family_name = data.get("family_name")
    family_side = data.get("family_side")
    auto_approve_threshold = data.get("auto_approve_threshold", 0.95)

    # Get config values outside generator
    db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))

    async def generate():
        try:
            db = GenealogyDatabase(db_path=db_path)
            session = db.get_session()

            try:
                # Get documents to reprocess
                if document_ids:
                    documents = session.query(Document).filter(Document.id.in_(document_ids)).all()
                else:
                    documents = session.query(Document).all()

                if not documents:
                    yield f"event: error\ndata: {json.dumps({'error': 'No documents found'})}\n\n"
                    return

                # Filter out documents without OCR text
                documents_with_ocr = [doc for doc in documents if doc.ocr_text]

                if not documents_with_ocr:
                    yield f"event: error\ndata: {json.dumps({'error': 'No documents with OCR text found'})}\n\n"
                    return

                total_documents = len(documents_with_ocr)

                # Send initial progress
                yield f"data: {json.dumps({'type': 'start', 'total': total_documents})}\n\n"

                # Initialize extractor and builder
                extractor = EntityExtractor(api_key=openai_key)
                builder = EntityBuilder(db=db, auto_approve_threshold=auto_approve_threshold)

                # Generate unique batch ID
                batch_id = generate_batch_id()

                # Track results
                total_staged = 0
                failed_documents = []

                # Process each document
                for idx, doc in enumerate(documents_with_ocr, 1):
                    try:
                        # Send progress update
                        yield f"data: {json.dumps({'type': 'progress', 'current': idx, 'total': total_documents, 'filename': Path(doc.source).name})}\n\n"

                        # Extract entities
                        extraction_result = extractor.extract(
                            text=doc.ocr_text,
                            source=doc.source,
                            page=doc.page or 1,
                        )

                        # Stage extraction results
                        if not extraction_result.is_empty():
                            counts = builder.stage_extraction(
                                extraction_result,
                                batch_id=batch_id,
                                document_id=doc.id,
                                family_name=family_name,
                                family_side=family_side,
                            )
                            total_staged += counts["people"]

                    except Exception as e:
                        import traceback

                        traceback.print_exc()
                        failed_documents.append(
                            {
                                "document_id": doc.id,
                                "source": doc.source,
                                "error": str(e),
                            }
                        )

                # Consolidate and match
                yield f"data: {json.dumps({'type': 'consolidating'})}\n\n"

                auto_approved = 0
                needs_review = 0
                review_ids = []

                if total_staged > 0:
                    processing_result = builder.process_batch(batch_id, auto_approve=True)
                    auto_approved = processing_result["auto_approved"]
                    needs_review = processing_result["needs_review"]
                    review_ids = processing_result["review_ids"]  # type: ignore[assignment]

                # Send completion
                yield f"data: {json.dumps({'type': 'complete', 'batch_id': batch_id, 'documents_processed': total_documents, 'documents_failed': len(failed_documents), 'entities_staged': total_staged, 'entities_auto_approved': auto_approved, 'entities_needs_review': needs_review, 'review_ids': review_ids, 'failed_documents': failed_documents})}\n\n"

            finally:
                session.close()

        except Exception as e:
            import traceback

            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
