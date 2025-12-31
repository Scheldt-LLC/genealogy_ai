"""Text chunking for OCR results.

This module chunks OCR text into manageable pieces for embedding and vector storage.
Chunks maintain references to their source documents for traceability.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from genealogy_ai.ingestion.ocr import OCRResult


@dataclass
class TextChunk:
    """A chunk of text with source metadata."""

    text: str
    source_path: Path
    page_number: int
    chunk_index: int
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "text": self.text,
            "source": str(self.source_path),
            "page": self.page_number,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


class DocumentChunker:
    """Chunk OCR results for embedding and vector storage."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ):
        """Initialize document chunker.

        Args:
            chunk_size: Maximum characters per chunk
            chunk_overlap: Number of characters to overlap between chunks
            separators: List of separators to use for splitting (default: paragraph/sentence)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Default separators prioritize logical breaks in genealogical documents
        self.separators = separators or [
            "\n\n",  # Paragraph breaks
            "\n",  # Line breaks
            ". ",  # Sentence endings
            ", ",  # Clause breaks
            " ",  # Word breaks
            "",  # Character breaks (fallback)
        ]

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.separators,
            length_function=len,
            is_separator_regex=False,
        )

    def chunk_ocr_result(self, ocr_result: OCRResult) -> list[TextChunk]:
        """Chunk a single OCR result.

        Args:
            ocr_result: OCR result to chunk

        Returns:
            List of TextChunk objects
        """
        if not ocr_result.text.strip():
            return []

        # Split the text
        chunks = self.text_splitter.split_text(ocr_result.text)

        # Create TextChunk objects with metadata
        text_chunks = []
        for i, chunk_text in enumerate(chunks):
            chunk = TextChunk(
                text=chunk_text,
                source_path=ocr_result.source_path,
                page_number=ocr_result.page_number,
                chunk_index=i,
                metadata={
                    "confidence": ocr_result.confidence,
                    "total_chunks": len(chunks),
                    **ocr_result.metadata,
                },
            )
            text_chunks.append(chunk)

        return text_chunks

    def chunk_ocr_results(self, ocr_results: list[OCRResult]) -> list[TextChunk]:
        """Chunk multiple OCR results.

        Args:
            ocr_results: List of OCR results to chunk

        Returns:
            List of all TextChunks from all results
        """
        all_chunks = []
        for ocr_result in ocr_results:
            chunks = self.chunk_ocr_result(ocr_result)
            all_chunks.extend(chunks)

        return all_chunks

    def create_page_summary(self, ocr_result: OCRResult, max_length: int = 500) -> str:
        """Create a summary of a page for context.

        Args:
            ocr_result: OCR result to summarize
            max_length: Maximum length of summary

        Returns:
            Summary text
        """
        text = ocr_result.text.strip()

        if len(text) <= max_length:
            return text

        # Take the first max_length characters and try to end at a sentence
        truncated = text[:max_length]
        last_period = truncated.rfind(". ")

        if last_period > max_length * 0.6:  # At least 60% of the text
            return truncated[: last_period + 1]

        return truncated + "..."

    def chunk_with_context(
        self, ocr_results: list[OCRResult], include_page_context: bool = True
    ) -> list[TextChunk]:
        """Chunk OCR results with optional page-level context.

        Args:
            ocr_results: List of OCR results
            include_page_context: Whether to add page summary to chunk metadata

        Returns:
            List of TextChunks with enhanced metadata
        """
        all_chunks = []

        for ocr_result in ocr_results:
            chunks = self.chunk_ocr_result(ocr_result)

            if include_page_context:
                page_summary = self.create_page_summary(ocr_result)
                for chunk in chunks:
                    chunk.metadata["page_summary"] = page_summary

            all_chunks.extend(chunks)

        return all_chunks
