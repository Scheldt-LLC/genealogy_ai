"""Document API endpoints."""

from pathlib import Path

from quart import Blueprint, current_app, jsonify, send_file

from src.backend.genealogy_ai.storage.sqlite import Document, GenealogyDatabase

documents_bp = Blueprint("documents", __name__)


@documents_bp.route("/api/documents", methods=["GET"])
async def list_documents() -> dict:
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
                source_path = Path(doc.source)
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
            documents_list.append({
                "id": pages_info["pages"][0],  # Use first page ID as document ID
                "filename": pages_info["filename"] or "Unknown",
                "file_path": pages_info["source"],
                "page_count": len(pages_info["pages"]),
                "created_at": pages_info["created_at"],
            })

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
async def get_document_file(document_id: int):
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

        file_path = Path(document.source)

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
