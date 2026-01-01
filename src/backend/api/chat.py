"""Chat API endpoints for querying genealogy data."""

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from quart import Blueprint, Response, current_app, jsonify, request

from src.backend.genealogy_ai.config import settings
from src.backend.genealogy_ai.storage.chroma import ChromaStore
from src.backend.genealogy_ai.storage.sqlite import Document, GenealogyDatabase

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/api/chat", methods=["POST"])
async def chat() -> Response | tuple[Response, int]:
    """Ask a question about the genealogy documents.

    Expects JSON body with:
        - question: The user's question

    Returns:
        JSON response with answer and source citations
    """
    try:
        data = await request.get_json()

        if not data or "question" not in data:
            return jsonify({"error": "No question provided"}), 400

        question = data["question"]

        if not question.strip():
            return jsonify({"error": "Question cannot be empty"}), 400

        # Initialize vector store
        chroma_dir = Path(current_app.config.get("CHROMA_DIR", "./chroma_db"))

        if not chroma_dir.exists():
            return jsonify(
                {
                    "error": "No documents have been indexed yet. Please upload and process documents first."
                }
            ), 400

        chroma_store = ChromaStore(persist_directory=chroma_dir)

        # Get API key
        try:
            api_key = settings.get_api_key()
        except ValueError as e:
            return jsonify({"error": f"OpenAI API key not configured: {e!s}"}), 500

        # Retrieve relevant documents
        retriever = chroma_store.vectorstore.as_retriever(search_kwargs={"k": 5})
        relevant_docs = retriever.invoke(question)

        # Build context from retrieved documents
        context_parts = []
        for i, doc in enumerate(relevant_docs, 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")
            context_parts.append(
                f"[Source {i}: {source}, Page {page}]\n{doc.page_content}\n"
            )

        context = "\n".join(context_parts)

        # Create LLM
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=SecretStr(api_key),
        )

        # Create prompt
        system_message = SystemMessage(
            content="""You are a helpful genealogy research assistant. Answer questions about genealogical documents based on the provided context.

If the context contains relevant information, provide a clear and concise answer.
If the context doesn't contain enough information to answer the question, say so.
Always cite the sources you use in your answer."""
        )

        user_message = HumanMessage(
            content=f"""Context from documents:
{context}

Question: {question}

Please answer the question based on the context provided above."""
        )

        # Get answer
        response = llm.invoke([system_message, user_message])

        # Get database connection to look up document IDs
        db_path = Path(current_app.config.get("DB_PATH", "./genealogy.db"))
        db = GenealogyDatabase(db_path=db_path)
        session = db.get_session()

        # Extract sources
        sources = []
        seen_sources = set()

        for doc in relevant_docs:
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")

            # Create unique identifier for deduplication
            source_id = f"{source}:{page}"

            if source_id not in seen_sources:
                seen_sources.add(source_id)

                # Look up document ID from database
                document_id = None
                db_doc = session.query(Document).filter(Document.source == source).first()
                if db_doc:
                    document_id = db_doc.id

                sources.append(
                    {
                        "source": source,
                        "page": page,
                        "document_id": document_id,
                        "text_preview": doc.page_content[:200] + "..."
                        if len(doc.page_content) > 200
                        else doc.page_content,
                    }
                )

        return jsonify(
            {
                "success": True,
                "question": question,
                "answer": response.content,
                "sources": sources,
            }
        ), 200

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Failed to process question: {e!s}"}), 500
