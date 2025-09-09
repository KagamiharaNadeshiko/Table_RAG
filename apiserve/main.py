from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from .routes.health import router as health_router
from .routes.cleanup import router as cleanup_router
from .routes.embeddings import router as embeddings_router
from .routes.data import router as data_router
from .routes.tables import router as tables_router
from .routes.chat import router as chat_router


def create_app() -> FastAPI:
    app = FastAPI(title="TableRAG API", version="0.1.0")
    # Enable permissive CORS for development; tighten in production as needed
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router, prefix="")
    app.include_router(cleanup_router, prefix="/cleanup", tags=["cleanup"])
    app.include_router(data_router, prefix="/data", tags=["data"])
    app.include_router(embeddings_router, prefix="/embeddings", tags=["embeddings"])
    app.include_router(tables_router, prefix="/tables", tags=["tables"])
    app.include_router(chat_router, prefix="/chat", tags=["chat"])

    # Serve minimal static frontend from apiserve/static
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app


app = create_app()


