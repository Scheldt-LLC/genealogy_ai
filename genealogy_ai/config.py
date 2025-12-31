"""Configuration management for Genealogy AI.

Loads settings from environment variables and provides validated configuration.
"""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load .env file if it exists
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Provider
    llm_provider: Literal["openai", "anthropic", "ollama"] = "openai"

    # OpenAI Configuration
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # Anthropic Configuration
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Azure OpenAI Configuration (for future cloud adapter)
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None

    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"

    # Database Paths
    db_path: Path = Path("./genealogy.db")
    chroma_dir: Path = Path("./chroma_db")
    ocr_output_dir: Path = Path("./ocr_output")

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_api_key(self) -> str:
        """Get the API key for the selected LLM provider.

        Returns:
            The API key for the current provider

        Raises:
            ValueError: If the API key is not set for the selected provider
        """
        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY not set. Please add it to your .env file. "
                    "Copy .env.example to .env and add your API key."
                )
            return self.openai_api_key

        if self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not set. Please add it to your .env file."
                )
            return self.anthropic_api_key

        if self.llm_provider == "ollama":
            # Ollama doesn't require an API key
            return ""

        raise ValueError(f"Unknown LLM provider: {self.llm_provider}")


# Global settings instance
settings = Settings()
