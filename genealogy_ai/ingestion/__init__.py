"""Ingestion module for OCR and document processing."""

from genealogy_ai.ingestion.chunking import DocumentChunker, TextChunk
from genealogy_ai.ingestion.ocr import OCRProcessor, OCRResult

__all__ = ["OCRProcessor", "OCRResult", "DocumentChunker", "TextChunk"]
