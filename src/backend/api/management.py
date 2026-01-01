"""Management API endpoints for database operations."""

from pathlib import Path

from quart import Blueprint, Response, current_app, jsonify

from src.backend.genealogy_ai.storage.chroma import ChromaStore
from src.backend.genealogy_ai.storage.sqlite import GenealogyDatabase

management_bp = Blueprint("management", __name__)


@management_bp.route("/api/documents/<int:document_id>", methods=["DELETE"])
async def delete_document(document_id: int) -> Response | tuple[Response, int]:
    """Delete a specific document and all its extracted data.

    Args:
        document_id: ID of the document to delete

    Returns:
        JSON response with success status
    """
    try:
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        # Get document info before deleting
        session = db.get_session()
        try:
            from src.backend.genealogy_ai.storage.sqlite import Document

            doc = session.query(Document).filter(Document.id == document_id).first()
            if not doc:
                return jsonify({"error": "Document not found"}), 404

            source_path = str(doc.source)
        finally:
            session.close()

        # Delete from SQLite
        db.delete_document(document_id)

        # Delete from ChromaDB
        try:
            chroma_dir = Path(current_app.config.get("CHROMA_DIR", "./chroma_db"))
            chroma_store = ChromaStore(persist_directory=chroma_dir)
            chroma_store.delete_by_source(Path(source_path))
        except Exception as e:
            # Log but don't fail if ChromaDB deletion fails
            print(f"Warning: Failed to delete from ChromaDB: {e}")

        return jsonify(
            {
                "success": True,
                "message": f"Document {document_id} deleted successfully",
            }
        ), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to delete document: {e!s}"}), 500


@management_bp.route("/api/reset", methods=["POST"])
async def reset_database() -> Response | tuple[Response, int]:
    """Reset the entire database (both SQLite and ChromaDB).

    WARNING: This will delete ALL data!

    Returns:
        JSON response with success status
    """
    try:
        # Reset SQLite
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        db.reset_database()

        # Reset ChromaDB
        chroma_dir = Path(current_app.config.get("CHROMA_DIR", "./chroma_db"))
        chroma_store = ChromaStore(persist_directory=chroma_dir)
        chroma_store.reset()

        return jsonify(
            {
                "success": True,
                "message": "Database reset successfully. All data has been deleted.",
            }
        ), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to reset database: {e!s}"}), 500
