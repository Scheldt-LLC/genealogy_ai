"""Main Quart application for Genealogy AI backend."""

from pathlib import Path

from quart import Quart, jsonify
from quart_cors import cors

from src.backend.config import get_config


def create_app(config_name: str = "development") -> Quart:
    """Create and configure the Quart application.

    Args:
        config_name: Configuration environment name

    Returns:
        Configured Quart app
    """
    app = Quart(__name__)

    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)

    # Enable CORS for frontend
    app = cors(
        app,
        allow_origin=config.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Ensure required directories exist
    Path(config.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(config.OCR_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Register blueprints/routes
    register_routes(app)

    return app


def register_routes(app: Quart) -> None:
    """Register API routes.

    Args:
        app: Quart application
    """

    @app.route("/", methods=["GET"])
    async def root():
        """Root endpoint - redirect to API info."""
        return jsonify(
            {
                "message": "Genealogy AI Backend",
                "version": "0.1.0",
                "api_docs": "/api/info",
            }
        )

    @app.route("/api/health", methods=["GET"])
    async def health_check():
        """Health check endpoint."""
        return jsonify(
            {
                "status": "healthy",
                "service": "genealogy-ai-backend",
                "version": "0.1.0",
            }
        )

    @app.route("/api/info", methods=["GET"])
    async def info():
        """Get API information."""
        return jsonify(
            {
                "service": "Genealogy AI API",
                "version": "0.1.0",
                "endpoints": {
                    "health": "/api/health",
                    "info": "/api/info",
                    "upload": "/api/upload (coming soon)",
                    "documents": "/api/documents (coming soon)",
                    "chat": "/api/chat (coming soon)",
                    "tree": "/api/tree (coming soon)",
                },
            }
        )


# Create app instance
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
