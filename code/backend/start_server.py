#!/usr/bin/env python3
"""
Startup script for the Silver Star FastAPI server.
This script sets up the Python path correctly before starting the server.
"""

import sys
from pathlib import Path
import copy

# Get the directory where this script is located
script_dir = Path(__file__).parent.absolute()
repo_root = script_dir.parent.parent
repo_root_str = str(repo_root.resolve())

# Ensure the backend app directory is on the Python path so the llm package
# resolves before any similarly named dependency.
app_root = script_dir / "app"
app_root_str = str(app_root.resolve())
if app_root_str not in sys.path:
    sys.path.insert(0, app_root_str)

# Ensure log directory exists for file logging
logs_dir = repo_root / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)
backend_log_file = logs_dir / "backend.log"


def bootstrap_log(message: str, *, error: bool = False) -> None:
    """Mirror important bootstrap messages to stdout/stderr and the backend log."""
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream)
    try:
        with backend_log_file.open("a", encoding="utf-8") as log_fp:
            log_fp.write(message + "\n")
    except Exception:
        # Logging should never block startup; swallow file write errors.
        pass


llm_path = app_root / "llm"
bootstrap_log(f"Adding {app_root_str} to Python path")
bootstrap_log(f"LLM directory exists: {llm_path.exists()}")
bootstrap_log(f"Repository root resolved to {repo_root_str}")

# Set up global error handling to terminate fast on errors
def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to terminate fast on errors."""
    import traceback
    bootstrap_log(f"Fatal error: {exc_type.__name__}: {exc_value}", error=True)
    bootstrap_log("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), error=True)
    sys.exit(1)

# Install the global exception handler
sys.excepthook = handle_exception

# Check if the llm module can be imported
try:
    import llm
    bootstrap_log("Successfully imported LLM module")
except ImportError as e:
    bootstrap_log(f"Error importing LLM module: {e}", error=True)
    bootstrap_log("Please ensure all dependencies are installed:", error=True)
    bootstrap_log("- google-generativeai", error=True)
    bootstrap_log("- google-cloud-speech", error=True)
    bootstrap_log("- google-cloud-texttospeech", error=True)
    sys.exit(1)

# Start the uvicorn server
if __name__ == "__main__":
    import uvicorn
    log_config = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
    log_config["handlers"]["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "level": "INFO",
        "formatter": "default",
        "filename": str(backend_log_file),
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 3,
    }

    # Attach file handler to default uvicorn loggers
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger_entry = log_config["loggers"].setdefault(logger_name, {})
        handlers = logger_entry.get("handlers", [])
        if "default" not in handlers:
            handlers.append("default")
        if "file" not in handlers:
            handlers.append("file")
        logger_entry["handlers"] = handlers

    # Ensure application logs also propagate
    log_config.setdefault("loggers", {}).setdefault("app", {
        "handlers": ["default", "file"],
        "level": "INFO",
        "propagate": False,
    })

    # Capture all framework and application warnings/errors at root level
    root_handlers = log_config.setdefault("root", {}).get("handlers", ["default"])
    if "file" not in root_handlers:
        root_handlers.append("file")
    log_config["root"]["handlers"] = root_handlers

    bootstrap_log(f"Backend logs will also be written to {backend_log_file}")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_config=log_config,
    )
