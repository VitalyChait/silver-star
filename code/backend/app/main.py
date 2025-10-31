import sys
import os

# Set up global error handling to terminate fast on errors
def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to terminate fast on errors."""
    import traceback
    print(f"Fatal error: {exc_type.__name__}: {exc_value}", file=sys.stderr)
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
    sys.exit(1)

# Install the global exception handler
sys.excepthook = handle_exception

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import json

from .config import settings
from .db import engine, Base
from .routers import jobs, auth, job_scraper

# Try to import the chatbot router, but don't fail if it can't be imported
try:
    from .routers import chatbot
    chatbot_available = True
    print("Chatbot module loaded successfully")
except ImportError as e:
    print(f"Warning: Could not import chatbot module: {e}", file=sys.stderr)
    print("Chatbot functionality will not be available.", file=sys.stderr)
    chatbot_available = False

# Try to import the craigslist router
try:
    from .routers import craigslist
    craigslist_available = True
    print("Craigslist module loaded successfully")
except ImportError as e:
    print(f"Warning: Could not import craigslist module: {e}", file=sys.stderr)
    print("Craigslist functionality will not be available.", file=sys.stderr)
    craigslist_available = False


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    # Capture environment-derived values once at startup
    startup_env = {
        "NODE_APP_PORT": int(os.getenv("NODE_APP_PORT", "3000")),
        "PYTHON_APP_PORT": int(os.getenv("PYTHON_APP_PORT", "8000")),
    }
    app.state.startup_env = startup_env

    # CORS for local dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_origin,
            f"http://localhost:{startup_env['NODE_APP_PORT']}",
            f"http://127.0.0.1:{startup_env['NODE_APP_PORT']}",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure tables exist (MVP)
    Base.metadata.create_all(bind=engine)

    # Routers
    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(job_scraper.router)
    
    # Only include the chatbot router if it was successfully imported
    if chatbot_available:
        app.include_router(chatbot.router)
    
    # Only include the craigslist router if it was successfully imported
    if craigslist_available:
        app.include_router(craigslist.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def root():
        return {"name": settings.app_name}

    # Expose frozen environment for frontend once per server start
    @app.get("/env.js")
    def env_js():
        payload = json.dumps(app.state.startup_env)
        body = f"window.__ENV__ = {payload}; Object.freeze(window.__ENV__);"
        return Response(content=body, media_type="application/javascript")

    return app


app = create_app()
