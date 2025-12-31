"""Main Quart application for Genealogy AI backend."""

from pathlib import Path

from quart import Quart, jsonify, send_from_directory
from quart_cors import cors

from src.backend.api.chat import chat_bp
from src.backend.api.documents import documents_bp
from src.backend.api.management import management_bp
from src.backend.api.upload import upload_bp
from src.backend.config import get_config


def create_app(config_name: str = "development") -> Quart:
    """Create and configure the Quart application.

    Args:
        config_name: Configuration environment name

    Returns:
        Configured Quart app
    """
    app = Quart(__name__, static_folder="static", static_url_path="")

    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)

    # Enable CORS for frontend (only needed in development)
    if config.DEBUG:
        app = cors(
            app,
            allow_origin=config.CORS_ORIGINS,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )

    # Ensure required directories exist
    Path(config.UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(config.OCR_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Register blueprints
    app.register_blueprint(upload_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(management_bp)

    # Register routes
    register_routes(app)

    return app


def register_routes(app: Quart) -> None:
    """Register API routes.

    Args:
        app: Quart application
    """

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
                    "upload": "/api/upload",
                    "documents": "/api/documents",
                    "chat": "/api/chat",
                    "tree": "/api/tree (coming soon)",
                },
            }
        )

    # Serve React app (production)
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    async def serve_react(path: str):
        """Serve the React frontend.

        In production, serves the built React app from static folder.
        In development, returns API info (frontend runs separately on Vite).
        """
        static_dir = Path(app.static_folder or "static")

        # Check if static folder exists (production build)
        if static_dir.exists():
            # Try to serve the requested file
            if path and (static_dir / path).exists():
                return await send_from_directory(static_dir, path)
            # Otherwise serve index.html (for React Router)
            if (static_dir / "index.html").exists():
                return await send_from_directory(static_dir, "index.html")

        # Development mode - no static build
        return jsonify(
            {
                "message": "Genealogy AI Backend",
                "version": "0.1.0",
                "note": "Frontend not built. Run 'npm run build' in src/frontend or use dev server.",
                "api_docs": "/api/info",
            }
        )


# Create app instance
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
