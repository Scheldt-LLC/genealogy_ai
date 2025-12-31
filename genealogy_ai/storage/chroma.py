"""Chroma vector database storage for document embeddings.

This module handles storage and retrieval of document chunks in ChromaDB.
Used for semantic search over OCR text and genealogical information.
"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from genealogy_ai.ingestion.chunking import TextChunk


class ChromaStore:
    """Vector database storage using Chroma."""

    def __init__(
        self,
        persist_directory: Path | None = None,
        collection_name: str = "genealogy_documents",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """Initialize Chroma vector store.

        Args:
            persist_directory: Directory to persist the database (default: ./chroma_db)
            collection_name: Name of the Chroma collection
            embedding_model: Name of the HuggingFace embedding model
        """
        self.persist_directory = persist_directory or Path("./chroma_db")
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name

        # Initialize embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        # Initialize Chroma client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # Initialize LangChain Chroma wrapper
        self.vectorstore = Chroma(
            client=self.client,
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
        )

    def add_chunks(self, chunks: list[TextChunk]) -> list[str]:
        """Add text chunks to the vector store.

        Args:
            chunks: List of TextChunk objects to add

        Returns:
            List of IDs for the added chunks
        """
        if not chunks:
            return []

        # Prepare documents and metadata
        texts = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "source": str(chunk.source_path),
                "page": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                **chunk.metadata,
            }
            for chunk in chunks
        ]

        # Generate IDs based on source, page, and chunk index
        ids = [
            f"{chunk.source_path.stem}_p{chunk.page_number}_c{chunk.chunk_index}"
            for chunk in chunks
        ]

        # Add to vector store
        self.vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)

        return ids

    def search(
        self,
        query: str,
        k: int = 5,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[tuple[str, dict[str, Any], float]]:
        """Search for similar chunks.

        Args:
            query: Search query
            k: Number of results to return
            filter_dict: Optional metadata filters

        Returns:
            List of (text, metadata, score) tuples
        """
        # Use similarity search with score
        results = self.vectorstore.similarity_search_with_score(
            query=query, k=k, filter=filter_dict
        )

        # Format results
        formatted_results = [
            (doc.page_content, doc.metadata, score) for doc, score in results
        ]

        return formatted_results

    def search_by_source(
        self, source_path: Path, query: str, k: int = 5
    ) -> list[tuple[str, dict[str, Any], float]]:
        """Search within a specific source document.

        Args:
            source_path: Path to the source document
            query: Search query
            k: Number of results to return

        Returns:
            List of (text, metadata, score) tuples
        """
        filter_dict = {"source": str(source_path)}
        return self.search(query, k=k, filter_dict=filter_dict)

    def get_by_source(self, source_path: Path) -> list[dict[str, Any]]:
        """Get all chunks from a specific source document.

        Args:
            source_path: Path to the source document

        Returns:
            List of chunk dictionaries with text and metadata
        """
        collection = self.client.get_collection(self.collection_name)
        results = collection.get(where={"source": str(source_path)})

        chunks = []
        for i, doc_id in enumerate(results["ids"]):
            chunks.append(
                {
                    "id": doc_id,
                    "text": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                }
            )

        return chunks

    def delete_by_source(self, source_path: Path) -> int:
        """Delete all chunks from a specific source document.

        Args:
            source_path: Path to the source document

        Returns:
            Number of chunks deleted
        """
        collection = self.client.get_collection(self.collection_name)
        results = collection.get(where={"source": str(source_path)})

        if results["ids"]:
            collection.delete(ids=results["ids"])
            return len(results["ids"])

        return 0

    def reset(self) -> None:
        """Reset the entire collection (USE WITH CAUTION)."""
        self.client.delete_collection(self.collection_name)
        self.vectorstore = Chroma(
            client=self.client,
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the vector store.

        Returns:
            Dictionary with collection statistics
        """
        collection = self.client.get_collection(self.collection_name)
        count = collection.count()

        # Get unique sources
        all_results = collection.get()
        sources = set()
        if all_results["metadatas"]:
            sources = {meta.get("source", "") for meta in all_results["metadatas"]}

        return {
            "total_chunks": count,
            "unique_sources": len(sources),
            "collection_name": self.collection_name,
            "persist_directory": str(self.persist_directory),
        }
