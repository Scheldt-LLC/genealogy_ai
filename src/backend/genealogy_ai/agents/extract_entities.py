"""Entity extraction agent for genealogical information.

This module uses an LLM to extract structured genealogical data
(people, events, relationships) from OCR'd document text.
"""

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.backend.genealogy_ai.config import settings
from src.backend.genealogy_ai.schemas import ExtractionResult


class EntityExtractor:
    """Extract genealogical entities from text using an LLM."""

    def __init__(
        self,
        model_name: str | None = None,
        temperature: float = 0.0,
        api_key: str | None = None,
    ):
        """Initialize the entity extractor.

        Args:
            model_name: Optional model name override
            temperature: LLM temperature (0.0 for deterministic, higher for creative)
            api_key: Optional API key override
        """
        self.model_name = model_name or settings.openai_model
        self.temperature = temperature

        # Load extraction prompt from genealogy_ai/prompts/
        prompt_path = Path(__file__).parent.parent / "prompts" / "extraction.md"
        with prompt_path.open() as f:
            self.system_prompt = f.read()

        # Initialize LLM based on provider
        if settings.llm_provider == "openai":
            final_api_key = api_key or settings.get_api_key()
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=SecretStr(final_api_key),
            )
        else:
            raise NotImplementedError(
                f"LLM provider {settings.llm_provider} not yet implemented. "
                "Currently only 'openai' is supported."
            )

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                (
                    "human",
                    "Extract genealogical information from the following document text:\n\n"
                    "Source: {source}\n"
                    "Page: {page}\n\n"
                    "Text:\n{text}\n\n"
                    "Return structured JSON following the format in the system prompt.",
                ),
            ]
        )

        # Create extraction chain with structured output
        self.chain = self.prompt | self.llm.with_structured_output(ExtractionResult)

    def extract(self, text: str, source: str, page: int) -> ExtractionResult:
        """Extract entities from document text.

        Args:
            text: The OCR'd text to extract from
            source: Source document path (for context)
            page: Page number (for context)

        Returns:
            ExtractionResult containing people, events, and relationships
        """
        if not text or not text.strip():
            return ExtractionResult()

        try:
            result: ExtractionResult = self.chain.invoke(
                {"text": text, "source": source, "page": page}
            )  # type: ignore[assignment]
            return result
        except Exception as e:
            # Log error and return empty result
            print(f"Extraction error for {source} page {page}: {e}")
            return ExtractionResult()

    def extract_batch(self, documents: list[tuple[str, str, int]]) -> list[ExtractionResult]:
        """Extract entities from multiple documents.

        Args:
            documents: List of (text, source, page) tuples

        Returns:
            List of ExtractionResult objects
        """
        results = []
        for text, source, page in documents:
            result = self.extract(text, source, page)
            results.append(result)
        return results
