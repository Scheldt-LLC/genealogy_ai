"""File upload API endpoints."""

import os
from pathlib import Path
from typing import Any

from quart import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from src.backend.genealogy_ai.ingestion.ocr import OCRProcessor
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
async def upload_file() -> tuple[dict[str, Any], int]:
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

    # Process with OCR
    try:
        ocr_output_dir = Path(current_app.config.get("OCR_OUTPUT_DIR", "./ocr_output"))
        ocr_processor = OCRProcessor(output_dir=ocr_output_dir)
        ocr_results = ocr_processor.process_document(file_path)

        # Save to database (one record per page)
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)

        document_ids = []
        for ocr_result in ocr_results:
            doc = db.add_document(
                source=str(ocr_result.source_path),
                page=ocr_result.page_number,
                ocr_text=ocr_result.text,
            )
            document_ids.append(doc.id)

        return jsonify(
            {
                "success": True,
                "document_ids": document_ids,
                "filename": filename,
                "page_count": len(ocr_results),
                "message": "File uploaded and processed successfully",
            }
        ), 201

    except Exception as e:
        # Clean up the file if processing failed
        if file_path.exists():
            os.remove(file_path)

        # Log full traceback for debugging
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to process file: {e!s}"}), 500
