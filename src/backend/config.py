"""Backend configuration for Genealogy AI web app."""

from pathlib import Path


class Config:
    """Base configuration."""

    # App settings
    DEBUG = True
    TESTING = False
    SECRET_KEY = "dev-secret-key-change-in-production"

    # CORS settings
    CORS_ORIGINS = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
    ]

    # File upload settings
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size
    UPLOAD_FOLDER = Path("./originals")
    ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".txt"}

    # Database paths
    DB_PATH = Path("./genealogy.db")
    CHROMA_DIR = Path("./chroma_db")
    OCR_OUTPUT_DIR = Path("./ocr_output")

    # Processing settings
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    MIN_CONFIDENCE = 0.6


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    # In production, load from environment variables
    SECRET_KEY = None  # Set via env var


# Config factory
def get_config(env: str = "development") -> Config:
    """Get configuration based on environment.

    Args:
        env: Environment name (development, production)

    Returns:
        Configuration object
    """
    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
    }
    return configs.get(env, DevelopmentConfig)()
