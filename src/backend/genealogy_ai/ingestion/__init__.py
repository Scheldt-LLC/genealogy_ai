"""Ingestion module for OCR and document processing."""

from src.backend.genealogy_ai.ingestion.chunking import DocumentChunker, TextChunk
from src.backend.genealogy_ai.ingestion.ocr import OCRProcessor, OCRResult

__all__ = ["OCRProcessor", "OCRResult", "DocumentChunker", "TextChunk"]
