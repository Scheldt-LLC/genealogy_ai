"""Document API endpoints."""

from pathlib import Path

from quart import Blueprint, current_app, jsonify

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
