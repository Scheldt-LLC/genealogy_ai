"""Document API endpoints."""

from pathlib import Path

from quart import Blueprint, Response, current_app, jsonify, request, send_file

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

        # Send the file
        return await send_file(
            file_path,
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
